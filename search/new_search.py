from enum import Enum
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from vision_msgs.msg import Detection2DArray
import numpy as np

IMAGE_WIDTH = 1400
IMAGE_HEIGHT = 1050  # Assuming standard aspect ratio

# Constants
TIMEOUT = 2.0  # seconds - threshold in timer_callback
SEARCH_YAW_VEL = 0.5  # rad/s - searching angular velocity
TRACK_FORWARD_VEL = 0.3  # m/s - tracking forward velocity
APPROACH_FORWARD_VEL = 0.2  # m/s - slower approach velocity
KP_YAW = 2.0  # proportional gain for yaw tracking
KP_FORWARD = 0.5  # proportional gain for forward movement

# Target thresholds
TARGET_BBOX_WIDTH = 300  # pixels - desired object width when close enough
TARGET_CENTER_TOLERANCE = 0.2  # normalized coordinates - how centered object should be
MIN_BBOX_WIDTH = 50  # pixels - minimum size to consider object valid

class State(Enum):
    SEARCH = 0
    TRACK = 1
    # APPROACH = 2
    # CENTERED = 3

class StateMachineNode(Node):
    def __init__(self, target_class_label):
        super().__init__('state_machine_node')
        
        self.target_class_label = str(target_class_label)
        self.get_logger().info(f'Tracking objects of class: {self.target_class_label}')

        self.detection_subscription = self.create_subscription(
            Detection2DArray,
            '/detections',
            self.detection_callback,
            10
        )

        self.command_publisher = self.create_publisher(
            Twist,
            'cmd_vel',
            10
        )

        self.timer = self.create_timer(0.1, self.timer_callback)
        self.state = State.SEARCH

        # Tracking variables
        self.last_tracked_object_x = 0.0  # normalized x coordinate [-1, 1]
        self.last_tracked_object_size = 0.0  # bbox width in pixels
        self.most_recent_detection = -float('inf')
        self.target_detected = False

    def detection_callback(self, msg):
        """
        Find the target class object that's closest to the last tracked position
        """
        target_detections = []
        
        # Filter detections for target class only
        print("All detections: ", [detection.results[0].hypothesis.class_id for detection in msg.detections])
        for detection in msg.detections:
            if detection.results:
                class_id = detection.results[0].hypothesis.class_id
                print("Hypothesis class id: ", detection.results[0].hypothesis.class_id)
                if class_id == self.target_class_label:
                    # Calculate normalized coordinates
                    x = detection.bbox.center.position.x
                   # x_normalized = (x - IMAGE_WIDTH/2) / (IMAGE_WIDTH/2)  # Convert to [-1, 1]
                    x_normalized = (x - 662) / (638 / 2)
                    bbox_width = detection.bbox.size_x
                    bbox_height = detection.bbox.size_y
                    
                    # Only consider detections with reasonable size
                    # if bbox_width > MIN_BBOX_WIDTH:
                    target_detections.append({
                        'x_norm': x_normalized,
                        'width': bbox_width,
                        'height': bbox_height,
                        'confidence': detection.results[0].hypothesis.score
                    })

        self.get_logger().info(f'Target detections: {target_detections}')

        if target_detections:
            self.most_recent_detection = self.get_clock().now().nanoseconds
            self.target_detected = True
            
            # Find the detection closest to the last tracked position
            best_detection = None
            min_distance = float('inf')
            
            for detection in target_detections:
                distance = abs(detection['x_norm'] - self.last_tracked_object_x)
                # Weight by confidence and size (prefer larger, more confident detections)
                weighted_distance = distance / (detection['confidence'] * np.sqrt(detection['width']))
                
                if weighted_distance < min_distance:
                    min_distance = weighted_distance
                    best_detection = detection
            
            if best_detection:
                self.last_tracked_object_x = best_detection['x_norm']
                self.last_tracked_object_size = best_detection['width']
                
                self.get_logger().info(
                    f'Tracking object: x={self.last_tracked_object_x:.2f}, '
                    f'size={self.last_tracked_object_size:.0f}px'
                )
        else:
            self.target_detected = False

    def timer_callback(self):
        """
        State machine logic with object-specific tracking and approach behavior
        """
        current_time = self.get_clock().now().nanoseconds
        time_since_detection = (current_time - self.most_recent_detection) / 1e9  # convert to seconds
        
        # State transitions
        if time_since_detection > TIMEOUT:
            self.state = State.SEARCH
        elif self.target_detected:
            # Check if object is centered and close enough
            is_centered = abs(self.last_tracked_object_x) < TARGET_CENTER_TOLERANCE
            # self.get_logger().info(f'Last tracked object x: {self.last_tracked_object_x}')
            is_close_enough = self.last_tracked_object_size > TARGET_BBOX_WIDTH
            
            # if is_centered and is_close_enough:
            #     self.state = State.CENTERED
            # elif is_close_enough:
            #     self.state = State.APPROACH  # Close but not centered
            # else:
                # self.state = State.TRACK  # Need to get closer
            self.state = State.TRACK  # track object
        
        # State actions
        yaw_command = 0.0
        forward_vel_command = 0.0
        
        if self.state == State.SEARCH:
            self.get_logger().info(f'State: SEARCHING for {self.target_class_label}')
            # Search in the direction where we last saw the object
            if self.last_tracked_object_x > 0:
                yaw_command = -SEARCH_YAW_VEL  # Turn left if object was on right
            else:
                yaw_command = SEARCH_YAW_VEL   # Turn right if object was on left
                
        elif self.state == State.TRACK:
            self.get_logger().info(f'State: TRACKING (size: {self.last_tracked_object_size:.0f}px)')
            # Turn towards object and move forward
            print("self.last_tracked_object_x", self.last_tracked_object_x)
            if abs(self.last_tracked_object_x) > TARGET_CENTER_TOLERANCE:
                yaw_command = -KP_YAW * self.last_tracked_object_x * 0.5
            else:
                yaw_command = 0
            forward_vel_command = 0
            
        # elif self.state == State.APPROACH:
        #     self.get_logger().info(f'State: APPROACHING (centering)')
        #     # Object is close, just center it
        #     yaw_command = -KP_YAW * self.last_tracked_object_x
        #     # Move forward slowly if not perfectly centered
        #     if abs(self.last_tracked_object_x) > TARGET_CENTER_TOLERANCE/2:
        #         forward_vel_command = APPROACH_FORWARD_VEL * 0.5
            
        # elif self.state == State.CENTERED:
        #     self.get_logger().info('State: CENTERED - Target reached!')
        #     # Stop - we're close and centered
        #     yaw_command = 0.0
        #     forward_vel_command = 0.0
        
        # Apply velocity limits and publish command
        yaw_command = np.clip(yaw_command, -1.0, 1.0)
        forward_vel_command = np.clip(forward_vel_command, 0.0, 0.5)
        
        cmd = Twist()
        cmd.angular.z = float(yaw_command)
        cmd.linear.x = float(forward_vel_command)
        self.command_publisher.publish(cmd)

def main(class_label=None):
    if class_label is None:
        print("Usage: Please provide a class label (e.g., '0' for person)")
        return
    
    rclpy.init()
    state_machine_node = StateMachineNode(class_label)

    try:
        rclpy.spin(state_machine_node)
    except KeyboardInterrupt:
        print("Program terminated by user")
    finally:
        # Send stop command
        zero_cmd = Twist()
        state_machine_node.command_publisher.publish(zero_cmd)
        
        state_machine_node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        target_class = sys.argv[1]
    else:
        target_class = '0'  # Default to person class
    main(target_class)