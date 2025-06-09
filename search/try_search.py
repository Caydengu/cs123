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

# Target thresholds
MIN_BBOX_WIDTH = 50  # pixels - minimum size to consider object valid

class State(Enum):
    SEARCH = 0
    DETECTED = 1

class StateMachineNode(Node):
    def __init__(self, target_class_label):
        super().__init__('state_machine_node')
        
        self.target_class_label = str(target_class_label)
        self.get_logger().info(f'Searching for objects of class: {self.target_class_label}')

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

        # Detection variables
        self.last_tracked_object_x = 0.0  # normalized x coordinate [-1, 1]
        self.most_recent_detection = -float('inf')
        self.target_detected = False

    def detection_callback(self, msg):
        """
        Check if target class object is detected
        """
        target_found = False
        
        # Look for target class in detections
        for detection in msg.detections:
            if detection.results:
                class_id = detection.results[0].hypothesis.class_id
                if class_id == self.target_class_label:
                    bbox_width = detection.bbox.size_x
                    
                    # Only consider detections with reasonable size
                    if bbox_width > MIN_BBOX_WIDTH:
                        target_found = True
                        
                        # Store last position for search direction
                        x = detection.bbox.center.position.x
                        self.last_tracked_object_x = (x - 662) / (638 / 2)
                        
                        self.get_logger().info(
                            f'Target detected: class={class_id}, '
                            f'x={self.last_tracked_object_x:.2f}, '
                            f'size={bbox_width:.0f}px'
                        )
                        break

        if target_found:
            self.most_recent_detection = self.get_clock().now().nanoseconds
            self.target_detected = True
        else:
            self.target_detected = False

    def timer_callback(self):
        """
        Simple state machine: SEARCH or DETECTED
        """
        current_time = self.get_clock().now().nanoseconds
        time_since_detection = (current_time - self.most_recent_detection) / 1e9  # convert to seconds
        
        # State transitions
        if time_since_detection > TIMEOUT:
            self.state = State.SEARCH
        elif self.target_detected:
            self.state = State.DETECTED
        
        # State actions
        yaw_command = 0.0
        forward_vel_command = 0.0
        
        if self.state == State.SEARCH:
            self.get_logger().info(f'State: SEARCHING for {self.target_class_label}')
            # Search in the direction opposite to where we last saw the object
            if self.last_tracked_object_x > 0:
                yaw_command = -SEARCH_YAW_VEL  # Turn left if object was on right
            else:
                yaw_command = SEARCH_YAW_VEL   # Turn right if object was on left
                
        elif self.state == State.DETECTED:
            self.get_logger().info(f'State: DETECTED - {self.target_class_label} found! Stopping.')
            # Stop all movement when target is detected
            yaw_command = 0.0
            forward_vel_command = 0.0
        
        # Publish command
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