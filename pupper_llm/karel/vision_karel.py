import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import Image
import pyttsx3
from openai import OpenAI
import karel  # Importing your KarelPupper API
import cv2
from cv_bridge import CvBridge
import base64
import io
from PIL import Image as PILImage
import numpy as np

client = OpenAI(api_key='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')

class GPT4ConversationNode(Node):
    def __init__(self):
        super().__init__('gpt4_conversation_node')

        # Create a subscriber to listen to user queries
        self.subscription = self.create_subscription(
            String,
            'user_query_topic',  # Replace with your topic name for queries
            self.query_callback,
            10
        )

        # Create a subscriber to listen to camera images
        self.image_subscription = self.create_subscription(
            Image,
            '/camera/image_raw',  # Camera topic from your launch file
            self.image_callback,
            10
        )

        # Create a publisher to send back responses
        self.publisher_ = self.create_publisher(
            String,
            'gpt4_response_topic',  # Replace with your topic name for responses
            10
        )

        self.get_logger().info('GPT-4o conversation node started and waiting for queries...')

        # Initialize the text-to-speech engine
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 150)  # Set the speed of speech (optional)

        # Initialize KarelPupper robot control
        self.pupper = karel.KarelPupper()

        # Initialize CV Bridge for image conversion
        self.bridge = CvBridge()
        
        # Store the latest image
        self.latest_image = None
        self.latest_image_timestamp = None

    def image_callback(self, msg):
        """Callback to process incoming camera images"""
        try:
            # Convert ROS Image message to OpenCV format
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            self.latest_image = cv_image
            self.latest_image_timestamp = self.get_clock().now()
            
            # Optionally log when we receive images
            # self.get_logger().info("Received camera image")
            
        except Exception as e:
            self.get_logger().error(f"Error processing camera image: {str(e)}")

    def encode_image_for_gpt(self, cv_image):
        """Convert OpenCV image to base64 string for GPT-4V"""
        try:
            # Convert BGR to RGB
            rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
            
            # Convert to PIL Image
            pil_image = PILImage.fromarray(rgb_image)
            
            # Resize image to reduce token usage (optional)
            # GPT-4V works well with smaller images
            max_size = 512
            if max(pil_image.size) > max_size:
                pil_image.thumbnail((max_size, max_size), PILImage.Resampling.LANCZOS)
            
            # Convert to base64
            buffer = io.BytesIO()
            pil_image.save(buffer, format="JPEG", quality=85)
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            return img_str
            
        except Exception as e:
            self.get_logger().error(f"Error encoding image: {str(e)}")
            return None

    def query_callback(self, msg):
        # Extract the user query from the message using the data attribute of message
        user_query = msg.data
        self.get_logger().info(f"Received user query: {user_query}")
        
        # Check if we should use vision (look for vision-related keywords)
        use_vision = any(keyword in user_query.lower() for keyword in 
                        ['see', 'look', 'what', 'where', 'describe', 'identify', 'find', 'detect', 'observe'])
        
        if use_vision and self.latest_image is not None:
            self.get_logger().info("Using vision-enabled GPT-4V for response")
            gpt_response = self.get_gpt4_vision_response(user_query)
        else:
            self.get_logger().info("Using text-only GPT-4 for response")
            gpt_response = self.get_gpt4_text_response(user_query)

        # Log the GPT-4o response
        self.get_logger().info(f"Published GPT-4o response: {gpt_response}")

        # Publish the response to the 'gpt4_response_topic'
        response_msg = String()
        response_msg.data = gpt_response
        self.publisher_.publish(response_msg)
        
        # Play the response through the speaker
        self.play_response(response_msg.data)
        
        # Parse and execute robot commands if present
        self.execute_robot_command(response_msg)

    def get_gpt4_vision_response(self, query):
        """Get response from GPT-4V using both text and image"""
        try:
            if self.latest_image is None:
                return "Sorry, no camera image available."
            
            # Encode the image
            base64_image = self.encode_image_for_gpt(self.latest_image)
            if base64_image is None:
                return "Sorry, couldn't process the camera image."

            prompt = """You are a control module for a robot dog with vision capabilities. 
            Your task is to interpret user commands that may involve visual information and 
            output a chain of basic commands from the list: 
            ["forward", "left", "right", "bark"].

- Always reply with one or more commands from the list, separated by spaces.
- Only use these four commands.
- Use the image to understand the environment and make appropriate movement decisions.
- If the user asks about what you see, describe it briefly then provide movement commands.
- If the user gives navigation instructions based on visual cues, interpret them into movement commands.

Examples:
- "Go toward the red object" → "forward forward"
- "Turn away from the wall" → "right"
- "Look for a person and go to them" → "left forward forward"
- "What do you see? Go around it." → "I see [description]. right forward forward left"

Always end with movement commands, space-separated."""

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system", 
                        "content": prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": query
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=300,
                temperature=0.7,
            )

            gpt_response = response.choices[0].message.content.strip()
            return gpt_response

        except Exception as e:
            self.get_logger().error(f"Error calling GPT-4V API: {str(e)}")
            return "Sorry, I couldn't process your request with vision."

    def get_gpt4_text_response(self, query):
        """Get response from GPT-4 using text only (original functionality)"""
        try:
            prompt = """You are a control module for a robot dog. 
            Your only task is to interpret user commands and 
            output a chain of basic commands from the list: 
            ["forward", "left", "right", "bark"].

- Always reply with one or more commands from the list, separated by spaces.
- Only use these four commands.
- Ignore all other information. Never reply with explanations or extra words.
- If the user gives a complex instruction, break it into a sequence of these commands.

Examples:
- "Walk forward and turn left." → "forward left"
- "Go forward twice, then bark." → "forward forward bark"
- "Turn right, then go forward three times." → "right forward forward forward"
- "Make a sound, then go in a square." → "bark forward right forward right forward right forward"

Always output only a list of commands, space-separated. Never explain."""

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": query},
                ],
                max_tokens=200,
                temperature=0.7,
            )

            gpt_response = response.choices[0].message.content.strip()
            return gpt_response

        except Exception as e:
            self.get_logger().error(f"Error calling GPT-4 API: {str(e)}")
            return "Sorry, I couldn't process your request."

    def play_response(self, response):
        try:
            # Use the TTS engine to say the response out loud
            self.tts_engine.say(response)
            self.tts_engine.runAndWait()
        except Exception as e:
            self.get_logger().error(f"Error playing response through speaker: {str(e)}")

    def execute_robot_command(self, response_msg):
        response = response_msg.data.lower().strip()
        self.get_logger().info(f"Executing command sequence: {response}")
        
        # Extract only the commands from the response (ignore any descriptive text)
        words = response.split()
        valid_commands = ['left', 'right', 'forward', 'bark']
        commands = [word for word in words if word in valid_commands]

        for command in commands:
            if command == 'left':
                self.pupper.turn_left()
            elif command == 'right':
                self.pupper.turn_right()
            elif command == 'forward':
                self.pupper.move()
            elif command == 'bark':
                self.pupper.bark()
            else:
                self.get_logger().warn(f"Unknown command: {command}")

def main(args=None):
    rclpy.init(args=args)

    # Create the node and spin it
    gpt4_conversation_node = GPT4ConversationNode()
    rclpy.spin(gpt4_conversation_node)

    # Clean up and shutdown
    gpt4_conversation_node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()