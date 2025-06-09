import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import pyttsx3
from openai import OpenAI
import karel  # Importing your KarelPupper API
import os
import subprocess
from time import sleep

client = OpenAI(api_key='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')

coco_classes = {
    "person": 0,
    "bicycle": 1,
    "car": 2,
    "motorcycle": 3,
    "airplane": 4,
    "bus": 5,
    "train": 6,
    "truck": 7,
    "boat": 8,
    "traffic light": 9,
    "fire hydrant": 10,
    "stop sign": 11,
    "parking meter": 12,
    "bench": 13,
    "bird": 14,
    "cat": 15,
    "dog": 16,
    "horse": 17,
    "sheep": 18,
    "cow": 19,
    "elephant": 20,
    "bear": 21,
    "zebra": 22,
    "giraffe": 23,
    "backpack": 24,
    "umbrella": 25,
    "handbag": 26,
    "tie": 27,
    "suitcase": 28,
    "frisbee": 29,
    "skis": 30,
    "snowboard": 31,
    "sports ball": 32,
    "kite": 33,
    "baseball bat": 34,
    "baseball glove": 35,
    "skateboard": 36,
    "surfboard": 37,
    "tennis racket": 38,
    "bottle": 39,
    "wine glass": 40,
    "cup": 41,
    "fork": 42,
    "knife": 43,
    "spoon": 44,
    "bowl": 45,
    "banana": 46,
    "apple": 47,
    "sandwich": 48,
    "orange": 49,
    "broccoli": 50,
    "carrot": 51,
    "hot dog": 52,
    "pizza": 53,
    "donut": 54,
    "cake": 55,
    "chair": 56,
    "couch": 57,
    "potted plant": 58,
    "bed": 59,
    "dining table": 60,
    "toilet": 61,
    "tv": 62,
    "laptop": 63,
    "mouse": 64,
    "remote": 65,
    "keyboard": 66,
    "cell phone": 67,
    "microwave": 68,
    "oven": 69,
    "toaster": 70,
    "sink": 71,
    "refrigerator": 72,
    "book": 73,
    "clock": 74,
    "vase": 75,
    "scissors": 76,
    "teddy bear": 77,
    "hair drier": 78,
    "toothbrush": 79
}


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

    # TODO: Implement the query_callback method
    # msg is a String message object that contains the user query. You can extract the query using msg.data
    def query_callback(self, msg):
        # Extract the user query from the message using the data attribute of message
        user_query = msg.data
        self.get_logger().info(f"Received user query: {user_query}")
        # Call GPT-4o API to get the response. Use the get_gpt4_response method and pass in the query
        
        prompt = f"""
        You are a classification module for an image recognition system.  
Your only task is to read the user's input and classify the object into one of the KEYS in this dictionary. Return the corresponding VALUE
for the key in:  {coco_classes}


- Always reply with only one numeric class label from the list.
- Only use exactly one of the list.
- Ignore all other information. Never reply with explanations or extra words.
- If the input is ambiguous or contains multiple objects, pick the most prominent one.

Examples:
- "This object is used for sitting." → "56"
- "It displays moving pictures." → "62"
- "You carry things in it on your back." → "24"
- "A student carries this to school." → "24"
- "You watch shows on this device." → "62"
- "Something with four legs you sit on." → "56"

Always output only one number: the predicted class label.
"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o",  # or use "gpt-3.5-turbo" or another model
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_query},
                ],
                max_tokens=200,
                temperature=0.7,
            )

            # Extract the assistant's message from the response
            gpt_response = response.choices[0].message.content.strip()

        except Exception as e:
            gpt_response = f"Error getting response from GPT-4o: {str(e)}"
            self.get_logger().error(gpt_response)

        # Log the GPT-4o response
        self.get_logger().info(f"Published GPT-4o response: {gpt_response}")

        # Publish the response to the 'gpt4_response_topic'
        response_msg = String()
        response_msg.data = gpt_response
        # Publish the response (as the data to a String message) using self.publisher_ and its publish method, 

        self.publisher_.publish(response_msg) # Publish the response to the ROS2 topic
        # Paste in your implementation from simple_gpt_chat.py
        
        # Play the response through the speaker with the play_response method
        self.play_response(response_msg.data)
       # print('Response: ', response)
        # Parse and execute robot commands if present with the execute_robot_command method
        self.execute_robot_command(response_msg)

    
    def play_response(self, response):
        try:
            # Use the TTS engine to say the response out loud
            self.tts_engine.say(response)
            self.tts_engine.runAndWait()
        except Exception as e:
            self.get_logger().error(f"Error playing response through speaker: {str(e)}")


    def extract_class_label(self, response_msg):
        response = response_msg.data.lower().strip()
        class_num = int(response)

        if 0 <= class_num <= 79:
            self.get_logger().info(f"Received classification response: {response}")
            return str(class_num)

        else:
            self.get_logger().warn(f"No valid class label found in response: {response}")
            return None


    def execute_robot_command(self, response_msg):
        class_label = self.extract_class_label(response_msg)
        print(f"Executing search for class label: {class_label}")

        
        if 0 <= int(class_label) <= 79:
            print("———————————")
            print(f"VALID CLASS LABEL RETURNED {class_label}")
            print("———————————")
            try:
                # Run the search.py script with the class label as argument
                script_path = os.path.join(os.path.expanduser("~"), "pupper_llm", "search", "search.py")
                subprocess.run(["python3", script_path, class_label], check=True)
            except subprocess.CalledProcessError as e:
                self.get_logger().error(f"Error running search.py: {str(e)}")
            except Exception as e:
                self.get_logger().error(f"Unexpected error: {str(e)}")
        else:
            pass

       

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
