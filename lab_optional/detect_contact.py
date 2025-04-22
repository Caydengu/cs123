import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray
import numpy as np

np.set_printoptions(precision=3, suppress=True)

pd_timer_period = 1.0 / 200  # 1 / x  means x Hz
ik_timer_period = 1.0 / 50   

class InverseKinematics(Node):
    def __init__(self):
        super().__init__('inverse_kinematics')

        self.joint_subscription = self.create_subscription(
            JointState,
            'joint_states',
            self.listener_callback,
            10
        )

        self.command_publisher = self.create_publisher(
            Float64MultiArray,
            '/forward_command_controller/commands',
            10
        )

        self.pd_timer_period = pd_timer_period
        self.ik_timer_period = ik_timer_period

        self.pd_timer = self.create_timer(self.pd_timer_period, self.pd_timer_callback)
        self.ik_timer = self.create_timer(self.ik_timer_period, self.ik_timer_callback)

        self.joint_positions = None
        self.joint_velocities = None
        self.target_joint_positions = None

        self.ee_triangle_positions = np.array([
            [0.05, 0.0, -0.12],   # Touchdown
            [-0.05, 0.0, -0.12],  # Liftoff
            [0.0, 0.0, -0.06]     # Mid-swing
        ]) + np.array([0.07500, -0.08350, 0])  # Offset from center to RF hip

        self.t = 0  # Timer for trajectory

        self.joint_state_history = np.zeros((200, 9))  # [position, velocity, effort] x 3 joints
        self.joint_state_index = 0
        self.joint_state_full = False

    def listener_callback(self, msg):
        joints_of_interest = ['leg_front_r_1', 'leg_front_r_2', 'leg_front_r_3']
        self.joint_positions = np.array([msg.position[msg.name.index(j)] for j in joints_of_interest])
        self.joint_velocities = np.array([msg.velocity[msg.name.index(j)] for j in joints_of_interest])
        
        try:
            positions = np.array([msg.position[msg.name.index(j)] for j in joints_of_interest])
            velocities = np.array([msg.velocity[msg.name.index(j)] for j in joints_of_interest])
            efforts = np.array([msg.effort[msg.name.index(j)] for j in joints_of_interest])
        except (ValueError, IndexError) as e:
            self.get_logger().warn(f"Missing joint state data: {e}")
            return

        combined = np.concatenate((positions, velocities, efforts))  # shape (9,)

        # Update rolling buffer
        self.joint_state_history[self.joint_state_index % 200] = combined
        self.joint_state_index += 1
        if self.joint_state_index >= 200:
            self.joint_state_full = True
    
    def get_recent_joint_states(self):
        if not self.joint_state_full:
            return self.joint_state_history[:self.joint_state_index]
        idx = self.joint_state_index % 200
        return np.vstack((self.joint_state_history[idx:], self.joint_state_history[:idx]))

    def forward_kinematics(self, theta1, theta2, theta3):
        """Compute end-effector position from joint angles."""
        def rot_x(a): return np.array([
            [1, 0, 0, 0],
            [0, np.cos(a), -np.sin(a), 0],
            [0, np.sin(a), np.cos(a), 0],
            [0, 0, 0, 1]
        ])

        def rot_y(a): return np.array([
            [np.cos(a), 0, np.sin(a), 0],
            [0, 1, 0, 0],
            [-np.sin(a), 0, np.cos(a), 0],
            [0, 0, 0, 1]
        ])

        def rot_z(a): return np.array([
            [np.cos(a), -np.sin(a), 0, 0],
            [np.sin(a), np.cos(a), 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ])

        def trans(x, y, z): return np.array([
            [1, 0, 0, x],
            [0, 1, 0, y],
            [0, 0, 1, z],
            [0, 0, 0, 1]
        ])

        T_0_1 = trans(0.07500, -0.0445, 0) @ rot_x(1.57080) @ rot_z(theta1)
        T_1_2 = trans(0, 0, 0.039) @ rot_y(-1.57080) @ rot_z(theta2)
        T_2_3 = trans(0, -0.0494, 0.0685) @ rot_y(1.57080) @ rot_z(theta3)
        T_3_ee = trans(0.06231, -0.06216, 0.018)

        T_0_ee = T_0_1 @ T_1_2 @ T_2_3 @ T_3_ee
        end_effector_position = T_0_ee @ np.array([[0], [0], [0], [1]])
        return end_effector_position[:3].flatten()

    def inverse_kinematics(self, target_ee, initial_guess=[0, 0, 0]):
        """Find joint angles that reach the desired end-effector position."""
        def cost_function(theta):
            ee_pos = self.forward_kinematics(*theta)
            error = ee_pos - target_ee
            return np.sum(error**2), np.sum(np.abs(error))

        def gradient(theta, eps=1e-3):
            grad = np.zeros(len(theta))
            for i in range(len(theta)):
                t_plus = theta.copy()
                t_plus[i] += eps
                c_plus, _ = cost_function(t_plus)

                t_minus = theta.copy()
                t_minus[i] -= eps
                c_minus, _ = cost_function(t_minus)

                grad[i] = (c_plus - c_minus) / (2 * eps)
            return grad

        theta = np.array(initial_guess)
        lr = 10
        max_iter = 20
        tol = 1e-2

        for _ in range(max_iter):
            grad = gradient(theta)
            theta -= lr * grad
            _, err = cost_function(theta)
            if err < tol:
                break
        return theta

    def interpolate_triangle(self, t):
        """Interpolate along a triangle-shaped trajectory."""
        t = t % 3
        i = int(t)
        p1 = self.ee_triangle_positions[i % 3]
        p2 = self.ee_triangle_positions[(i + 1) % 3]
        alpha = t % 1
        return p1 + alpha * (p2 - p1)

    def ik_timer_callback(self):
        if self.joint_positions is not None:
            target_ee = self.interpolate_triangle(self.t)
            self.target_joint_positions = self.inverse_kinematics(target_ee, self.joint_positions)
            current_ee = self.forward_kinematics(*self.joint_positions)
            self.t += self.ik_timer_period 

            '''
            self.get_logger().info(
                f'Target EE: {target_ee}, '
                f'Current EE: {current_ee}, '
                f'Target Angles: {self.target_joint_positions}, '
                f'Target EE Check: {self.forward_kinematics(*self.target_joint_positions)}, '
                f'Current Angles: {self.joint_positions}'
            )
            '''

    def pd_timer_callback(self):
        if self.target_joint_positions is not None:
            msg = Float64MultiArray()
            msg.data = self.target_joint_positions.tolist()
            self.command_publisher.publish(msg)

def main():
    rclpy.init()
    node = InverseKinematics()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("Program terminated by user")
    finally:
        msg = Float64MultiArray()
        msg.data = [0.0, 0.0, 0.0]
        node.command_publisher.publish(msg)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
