from enum import Enum
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from vision_msgs.msg import Detection2DArray
import numpy as np

IMAGE_WIDTH = 1400
# TODO: Add your new constants here

TIMEOUT = 2 #TODO threshold in timer_callback
SEARCH_YAW_VEL = 0.5 #TODO searching constant
TRACK_FORWARD_VEL = 0.5 #TODO tracking constant
KP = 2 #TODO proportional gain for tracking

class State(Enum):
    SEARCH = 0
    TRACK = 1

class StateMachineNode(Node):
    def __init__(self):
        super().__init__('state_machine_node')

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
        self.state = State.TRACK

        # TODO: Add your new member variables here
        

        self.last_tracked_object_x = 0
        self.most_recent_detection = -float('inf')

    def detection_callback(self, msg):
        """
        Determine which of the HAILO detections is the most central detected object
        """

        if msg.detections:
            self.most_recent_detection = self.get_clock().now().nanoseconds
           # print(self.get_clock().now())
        else:
            return 
        
        candidate, dist_min  = None, float('inf')
        for i, detection in enumerate(msg.detections):
            x = detection.bbox.center.position.x
            x = (x / IMAGE_WIDTH - 0.5) * 2
            
            if abs(x - self.last_tracked_object_x) < dist_min:
                dist_min = abs(x - self.last_tracked_object_x)
                candidate = x
        self.last_tracked_object_x = candidate
       # print(f'tracked object normalized x coordinate: {candidate}')

    def timer_callback(self):
        """
        Implement a timer callback that sets the moves through the state machine based on if the time since the last detection is above a threshold TIMEOUT
        """
        
        if self.get_clock().now().nanoseconds - self.most_recent_detection > 1e9 * TIMEOUT: # in nanoseconds 1e9 ns = 1 s  # TODO: Part 3.2
            self.state = State.SEARCH
            print('search')
        else:
            self.state = State.TRACK
            print('track')

        yaw_command = 0.0
        forward_vel_command = 0.0

        if self.state == State.SEARCH:
            if self.last_tracked_object_x > 0:
                yaw_command = - SEARCH_YAW_VEL
            else:
                yaw_command = SEARCH_YAW_VEL
        elif self.state == State.TRACK:
            yaw_command = - KP * self.last_tracked_object_x
            forward_vel_command = TRACK_FORWARD_VEL

        cmd = Twist()
        cmd.angular.z = yaw_command
        cmd.linear.x = forward_vel_command
        self.command_publisher.publish(cmd)

def main():
    rclpy.init()
    state_machine_node = StateMachineNode()

    try:
        rclpy.spin(state_machine_node)
    except KeyboardInterrupt:
        print("Program terminated by user")
    finally:
        zero_cmd = Twist()
        state_machine_node.command_publisher.publish(zero_cmd)

        state_machine_node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
