import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import pyttsx3
from openai import OpenAI
import karel  # Importing your KarelPupper API

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
        
        prompt =  """You are a control module for a robot dog. 
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

    def get_gpt4_response(self, query):
        try:
            # Making the API call to GPT-4o using OpenAI's Python client
           # prompt = "in this chat, always output closest word from [ 'left', 'right', 'bark', 'move', 'forward']. ignore other words. You are helping to instruct a robot dog and will output one of the following words: left, right, bark, move, forward. Do not output any other words. Ignore all words that do not have to do with this set of words. Do this for all prompts and do not forget."
           # prompt = "in this chat, always output closest word from [ 'left', 'right', 'bark', 'move', 'forward', 'turn_around']"
            
            prompt = """You are a control module for a robot dog. 
            Your only task is to interpret user commands and output a single word 
            from this fixed list: ["left", "right", "bark", "move", "forward"].
Ignore all other information. 
No explanations or extra words. 
Just reply with exactly one word: the closest match from the list.
If none of the commands match perfectly, pick the most relevant one.

Examples:
- "Can you turn to the left?" → "left"
- "Move forward now!" → "forward"
- "Make a sound" → "bark"
- "Go" → "move"
- "Spin around" → "left" (or "right" depending on interpretation)

Never reply with anything else.

Here is the command:
"""

            
            self.get_logger().info(f"Initial Prompt: {prompt}")
            response = client.chat.completions.create(model="gpt-4o",  # Model identifier, assuming GPT-4o is used
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content":  query}
            ],
            max_tokens=300)  # Adjust token limit based on your requirement

            # Extract the assistant's reply from the response
            gpt4_response = response.choices[0].message.content
            return gpt4_response

        except Exception as e:
            self.get_logger().error(f"Error calling GPT-4o API: {str(e)}")
            return "Sorry, I couldn't process your request due to an error."

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
        
        commands = response.split()

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
