data_dir = '/home/c-lhy/cs123/data/tactile_data'
# saved model info:
# val | Contact Acc: 0.9606 | Incline Acc: 0.9164 | Material Acc: 0.8763
import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import pickle
import random
import copy
import numpy as np
import pandas as pd
from tqdm.auto import tqdm
from torch.utils.data import Dataset
from scipy.interpolate import interp1d
from sklearn.metrics import accuracy_score
from torch.utils.data import Dataset, DataLoader, random_split


class WindowedJointStateDataset(Dataset):
    def __init__(self, root_dir, window_size, window_stride):
        self.root_dir = root_dir
        self.window_size = window_size
        self.window_stride = window_stride
        self.incline_classes = [15, 30, 45, 60, 75, 0]
        self.material_classes = ['none', 'felt pad', 'rough', 'slip', 'very rough', 'foam']
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.windows = []

        for folder1 in os.listdir(root_dir):
            if folder1.startswith('.') or folder1 in ['reference_images', 'lookups'] or folder1 == 'explicit_train_dataset.csv':
                continue
            for folder2 in os.listdir(os.path.join(root_dir, folder1)):
                if folder2.startswith('.'):
                    continue
                folder_path = os.path.join(root_dir, folder1, folder2)
                if not os.path.isdir(folder_path):
                    continue

                incline_label, material_label = self._parse_folder_name(folder_path)
                if incline_label is None or material_label is None:
                    continue

                print(f"Processing {folder_path}")
                print(f"Incline: {self.incline_classes[incline_label]}, Material: {self.material_classes[material_label]}")
                self._process_folder(folder_path, incline_label, material_label)

    def _parse_folder_name(self, folder_name):
        incline_label = None
        material_label = None
        folder_lower = folder_name.lower()

        for i, incline in enumerate(self.incline_classes):
            if str(incline) in folder_lower:
                incline_label = i
                break

        for i, material in enumerate(self.material_classes):
            if material in folder_lower:
                material_label = i
                break

        if 'felt_pad' in folder_lower or 'felt pad' in folder_lower:
            material_label = self.material_classes.index('felt pad')
        elif 'very_rough' in folder_lower or 'very rough' in folder_lower:
            material_label = self.material_classes.index('very rough')

        return incline_label, material_label

    def _process_folder(self, folder_path, incline_label, material_label):
        js_file = os.path.join(folder_path, 'joint_states.csv')
        ct_file = os.path.join(folder_path, 'contact.csv')
        if not os.path.exists(js_file) or not os.path.exists(ct_file):
            return

        try:
            js = pd.read_csv(js_file).sort_values('timestamp')
            ct = pd.read_csv(ct_file).sort_values('timestamp')
        except Exception as e:
            print(f"Error loading files in {folder_path}: {e}")
            return

        if js.empty or ct.empty or len(js) < self.window_size:
            return

        interp_funcs = [
            interp1d(ct['timestamp'], ct.iloc[:, i+1], bounds_error=False, fill_value='extrapolate')
            for i in range(ct.shape[1] - 1)
        ]

        timestamps = js['timestamp'].values
        motor_states = js.drop(columns='timestamp').iloc[:, :9].values.astype(np.float32)

        contact_interp = np.array([[f(t) for f in interp_funcs] for t in timestamps], dtype=np.float32)
        contact_tensor = torch.tensor(contact_interp, device=self.device)
        contact_states = (contact_tensor.max(dim=1)[0] > 0.5).float().cpu().numpy()

        for i in range(0, len(motor_states) - self.window_size + 1, self.window_stride):
            self.windows.append({
                'motor_states': motor_states[i:i + self.window_size],
                'contact_state': int(np.mean(contact_states[i:i + self.window_size]) > 0.5),
                'contact_sequence': contact_states[i:i + self.window_size],
                'incline_label': incline_label,
                'material_label': material_label
            })

    def __len__(self):
        return len(self.windows)

    def __getitem__(self, idx):
        w = self.windows[idx]
        return {
            'motor_states': torch.tensor(w['motor_states'], dtype=torch.float32),
            'contact_state': torch.tensor(w['contact_state'], dtype=torch.float32),
            'contact_sequence': torch.tensor(w['contact_sequence'], dtype=torch.float32),
            'incline_label': torch.tensor(w['incline_label'], dtype=torch.long),
            'material_label': torch.tensor(w['material_label'], dtype=torch.long)
        }


def load_dataset(filename):
    """Load a previously processed dataset"""
    print(f"Loading dataset from {filename}")
    with open(filename, 'rb') as f:
        save_data = pickle.load(f)

    # Create an empty dataset (no processing)
    dataset = WindowedJointStateDataset.__new__(WindowedJointStateDataset)

    # Restore the saved attributes
    dataset.windows = save_data['windows']
    dataset.incline_classes = save_data['incline_classes']
    dataset.material_classes = save_data['material_classes']
    dataset.window_size = save_data['window_size']
    dataset.window_stride = save_data['window_stride']
    dataset.root_dir = ""  # Not used after loading

    print(f"Loaded dataset with {len(dataset.windows)} windows")
    return dataset

dataset = load_dataset(data_dir+'/lookups/processed_dataset.pkl')


class PCGrad:
    def __init__(self, optimizer, reduction='mean'):
        """
        Args:
            optimizer (torch.optim.Optimizer): Wrapped optimizer.
            reduction (str): Method to reduce gradients ('mean' or 'sum').
        """
        self._optim = optimizer
        self._reduction = reduction

    @property
    def optimizer(self):
        return self._optim

    def zero_grad(self):
        """Clear gradients of all optimized parameters."""
        self._optim.zero_grad()

    def step(self):
        """Performs a single optimization step."""
        self._optim.step()

    def pc_backward(self, objectives):
        """
        Compute backward pass using Projected Conflicting Gradient (PCGrad).

        Args:
            objectives (List[torch.Tensor]): List of scalar loss values.
        """
        grads, shapes, has_grads = self._pack_grad(objectives)        
        projected_grad = self._project_conflicting(grads, has_grads)
        unflattened_grad =  self._unflatten_grad(projected_grad, shapes[0])
        self._set_grad(unflattened_grad)

    # ---------- Internal Utilities ----------

    def _pack_grad(self, objectives):
        """
        Compute gradients for each objective.

        Returns:
            grads (List[Tensor]): Flattened gradients.
            shapes (List[Tuple]): Shapes of original parameters.
            has_grads (List[Tensor]): Masks indicating valid gradients.
        """
        grads, shapes, has_grads = [], [], []

        for obj in objectives:
            self._optim.zero_grad(set_to_none=True)
            obj.backward(retain_graph=True)
            grad, shape, has_grad = self._retrieve_grad()
            grads.append(self._flatten_grad(grad))
            has_grads.append(self._flatten_grad(has_grad))
            shapes.append(shape)

        return grads, shapes, has_grads

    def _retrieve_grad(self):
        """
        Retrieve gradients and shapes from the model parameters.

        Returns:
            grad (List[Tensor]): Gradient tensors.
            shape (List[Tuple]): Original parameter shapes.
            has_grad (List[Tensor]): Gradient masks.
        """
        grad, shape, has_grad = [], [], []

        for group in self._optim.param_groups:
            for p in group['params']:
                if p.grad is None:
                    shape.append(p.shape)
                    grad.append(torch.zeros_like(p))
                    has_grad.append(torch.zeros_like(p))
                else:
                    shape.append(p.grad.shape)
                    grad.append(p.grad.clone())
                    has_grad.append(torch.ones_like(p))

        return grad, shape, has_grad

    def _flatten_grad(self, grads):
        return torch.cat([g.flatten() for g in grads])

    def _unflatten_grad(self, flat_grads, shapes):
        unflattened, idx = [], 0
        for shape in shapes:
            length = np.prod(shape)
            unflattened.append(flat_grads[idx:idx + length].view(shape).clone())
            idx += length
        return unflattened

    def _set_grad(self, grads):
        """Assign updated gradients back to model parameters."""
        idx = 0
        for group in self._optim.param_groups:
            for p in group['params']:
                p.grad = grads[idx]
                idx += 1


    def _project_conflicting(self, grads, has_grads):
        """
        Resolve gradient conflicts via orthogonal projection.

        Args:
            grads (List[Tensor]): Flattened gradients.
            has_grads (List[Tensor]): Valid gradient masks.

        Returns:
            Tensor: Projected merged gradient.
        """
        shared = torch.stack(has_grads).prod(0).bool()
        pc_grad = copy.deepcopy(grads)
        for g_i in pc_grad:
            random.shuffle(grads)
            for g_j in grads:
                """
                TODO: Implement the gradient surgery step
                """
                gi_shared = g_i[shared]
                gj_shared = g_j[shared]
                if torch.dot(gi_shared, gj_shared) < 0:
                    proj = (torch.dot(gi_shared, gj_shared) / (gj_shared.norm() ** 2 + 1e-12)) * gj_shared
                    g_i[shared] -= proj

        merged = torch.zeros_like(grads[0])

        # Handle weights with all contributing gradients
        if self._reduction == 'mean':
            merged[shared] = torch.stack([g[shared] for g in pc_grad]).mean(dim=0)
        elif self._reduction == 'sum':
            merged[shared] = torch.stack([g[shared] for g in pc_grad]).sum(dim=0)
        else:
            raise ValueError("Invalid reduction method")
        # Sum up weights with some non-contributing gradients for stability
        merged[~shared] = torch.stack([g[~shared] for g in pc_grad]).sum(dim=0)
        return merged





class JointStateCNN(torch.nn.Module):
    def __init__(self, input_channels=9, window_size=100):
        super().__init__()

        # 1D Convolutional layers (along time dimension)
        """
        TODO: Implement 3 1D convolutional layers with proper activation functions,
              batch normalization, and pooling.
        """
         # Replace this with your own implementation
         # 1D Convolutional layers (along time dimension)
        self.conv1 = nn.Conv1d(input_channels, 32, kernel_size=5, padding=2)
        self.bn1 = nn.BatchNorm1d(32)
        self.pool1 = nn.MaxPool1d(kernel_size=2)

        self.conv2 = nn.Conv1d(32, 64, kernel_size=5, padding=2)
        self.bn2 = nn.BatchNorm1d(64)
        self.pool2 = nn.MaxPool1d(kernel_size=2)

        self.conv3 = nn.Conv1d(64, 128, kernel_size=3, padding=1)
        self.bn3 = nn.BatchNorm1d(128)
        self.pool3 = nn.MaxPool1d(kernel_size=2)

        # Calculate the size after convolutions and pooling
        output_size = window_size
        output_size = output_size // 2  # pool1
        output_size = output_size // 2  # pool2
        output_size = output_size // 2  # pool3

        # Fully connected layers
        self.fc1 = torch.nn.Linear(128 * output_size, 256)
        self.dropout = torch.nn.Dropout(0.5)

        # Output heads
        """
        TODO: Implement three separate output heads: contact_head, incline_head, and material_head.
              Each head should be a separate torch.nn.Linear layer.
              Think about the output dimensions for each head.
        """
        self.contact_head = nn.Linear(256, 1)         # Binary classification
        self.incline_head = nn.Linear(256, 6)         # 6 classes for incline
        self.material_head = nn.Linear(256, 6)        # 6 classes for material

    def forward(self, x):
        # x shape: [batch_size, window_size, input_channels]
        # Reshape for 1D convolution: [batch_size, input_channels, window_size]
        x = x.transpose(1, 2)


        '''
        TODO: Implement the forward pass through the convolutional layers.
        '''
        # Convolutional layers
        x = self.pool1(F.relu(self.bn1(self.conv1(x))))
        x = self.pool2(F.relu(self.bn2(self.conv2(x))))
        x = self.pool3(F.relu(self.bn3(self.conv3(x))))


        # Flatten
        x = x.view(x.size(0), -1)

        # Fully connected
        x = torch.nn.functional.relu(self.fc1(x))
        x = self.dropout(x)

        # Output heads
        return {
            'contact': torch.sigmoid(self.contact_head(x)),
            'incline': self.incline_head(x),
            'material': self.material_head(x)
        }

# Define the split ratio
train_ratio = 0.9
val_ratio = 1 - train_ratio

# Calculate the total size of the dataset
total_size = len(dataset)

# Compute the number of samples for training and validation
train_size = int(train_ratio * total_size)
val_size = total_size - train_size

# Use `random_split` to divide the dataset into training and validation subsets
train_subset, val_subset = random_split(dataset, [train_size, val_size])

# Create DataLoaders for both training and validation subsets. Set batch size to 512.
dataloaders = {
    'train': DataLoader(train_subset, batch_size=512, shuffle=True),
    'val': DataLoader(val_subset, batch_size=512, shuffle=False)
}

# Print the sizes of the splits
print(f"Dataset split into train ({train_size}) and val ({val_size}) successfully!")


device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using device: {device}")

model = JointStateCNN(input_channels=9, window_size=dataset.window_size).to(device)

bce = torch.nn.BCELoss()
ce = torch.nn.CrossEntropyLoss(reduction='none')

base_optim = torch.optim.Adam(model.parameters(), lr=1e-3)
optimizer = PCGrad(base_optim)
num_epochs = 200 #original num_epochs = 50

for epoch in range(1, num_epochs + 1):
    print(f"\nEpoch {epoch}/{num_epochs}")

    contact_weight = max(0.1, 1.0 - (epoch - 1) / (num_epochs - 1))  # Linear decay

    for phase in ['train', 'val']:
        model.train() if phase == 'train' else model.eval()

        contact_preds, contact_targets = [], []
        incline_preds, incline_targets = [], []
        material_preds, material_targets = [], []

        for batch in tqdm(dataloaders[phase], desc=f"{phase.capitalize()} Epoch {epoch}"):
            x = batch['motor_states'].to(device)
            y_contact = batch['contact_state'].unsqueeze(1).to(device)
            y_incline = batch['incline_label'].to(device)
            y_material = batch['material_label'].to(device)

            if phase == 'train':
                optimizer.zero_grad()

            with torch.set_grad_enabled(phase == 'train'):
                out = model(x)

                loss_contact = bce(out['contact'], y_contact)

                mask = y_contact.bool().float().squeeze()
                loss_incline = ce(out['incline'], y_incline)
                loss_material = ce(out['material'], y_material)

                masked_incline = torch.nan_to_num((loss_incline * mask).mean(), nan=0.0)
                masked_material = torch.nan_to_num((loss_material * mask).mean(), nan=0.0)

                '''
                TODO: Apply the decaying weight to the contact loss.
                Only include incline and material losses in the objectives list
                if there are valid contact labels in the batch (i.e., contact is True).
                Then pass the selected objectives to the PCGrad optimizer to perform
                gradient surgery and update the model.
                '''
                # Apply the decaying weight to the contact loss
                weighted_contact_loss = contact_weight * loss_contact

                # Create list of objectives for PCGrad
                objectives = [weighted_contact_loss]

                if masked_incline.item() > 0:
                    objectives.append(masked_incline)
                if masked_material.item() > 0:
                    objectives.append(masked_material)

                if phase == 'train':
                    optimizer.pc_backward(objectives)
                    optimizer.step()

            contact_preds.extend((out['contact'] > 0.5).float().cpu().numpy().flatten())
            contact_targets.extend(y_contact.cpu().numpy().flatten())

            contact_indices = mask.cpu().numpy().astype(bool)
            if contact_indices.any():
                incline_preds.extend(torch.argmax(out['incline'], dim=1).cpu().numpy()[contact_indices])
                incline_targets.extend(y_incline.cpu().numpy()[contact_indices])
                material_preds.extend(torch.argmax(out['material'], dim=1).cpu().numpy()[contact_indices])
                material_targets.extend(y_material.cpu().numpy()[contact_indices])

        # Compute and print metrics
        contact_acc = accuracy_score(contact_targets, contact_preds)
        incline_acc = accuracy_score(incline_targets, incline_preds) if incline_targets else 0
        material_acc = accuracy_score(material_targets, material_preds) if material_targets else 0

        print(f"{phase} | Contact Acc: {contact_acc:.4f} | Incline Acc: {incline_acc:.4f} | Material Acc: {material_acc:.4f}")

"""### ✅ Results & Reflections

By tuning various training parameters, we were able to achieve:

- **~95% accuracy** on contact detection  
- **~90% accuracy** on slope incline classification  
- **~80% accuracy** on surface material classification  

Surprisingly, these results show that joint state readings alone — without any high-end tactile sensors — can be remarkably effective for terrain understanding. This highlights the potential of proprioceptive sensing as a lightweight, low-cost alternative for real-time contact reasoning in legged robots.

"""
torch.save(model.state_dict(), '/home/c-lhy/cs123/implicit_model.pt')
print(f'model saved at {data_dir}.')