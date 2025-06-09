import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from openai import OpenAI

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


    
    # TODO: Implement the query_callback method
    # msg is a String message object that contains the user query. You can extract the query using msg.data
    def query_callback(self, msg):

        # Extract the user query from the message using the data attribute of message
        user_query = msg.data
        self.get_logger().info(f"Received user query: {user_query}")
        # Call GPT-4o API to get the response. Use the get_gpt4_response method and pass in the query
        try:
            response = client.chat.completions.create(
                model="gpt-4o",  # or use "gpt-3.5-turbo" or another model
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
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
        

    def get_gpt4_response(self, query):
        try:
            # Making the API call to GPT-4o using OpenAI's Python client
            prompt = "do the commands that I will say later exactly without modification"
            self.get_logger().info(f"Initial Prompt: {prompt}")
            response = client.chat.completions.create(model="gpt-4o",  # Model identifier, assuming GPT-4o is used
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": query}
            ],
            max_tokens=150)  # Adjust token limit based on your requirement)

            # Extract the assistant's reply from the response
            gpt4_response = response.choices[0].message.content
            return gpt4_response

        except Exception as e:
            self.get_logger().error(f"Error calling GPT-4o API: {str(e)}")
            return "Sorry, I couldn't process your request due to an error."

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
