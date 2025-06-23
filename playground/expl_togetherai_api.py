"""
This script is an exploration of the TogetherAI API for learning purposes. It is not intended to be a complete list of available API endpoints or their functionalities.
"""

from together import Together
import os
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    try:
        client = Together(api_key=os.environ["TOGETHER_API_KEY"])
    except AttributeError:
        print("Error: The TOGETHER_API_KEY environment variable is not set.")
        print("Please set your API key as an environment variable.")
        exit()

    response = client.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
        messages=[
            {
                "role": "user",
                "content": "What is the capital of France?"
            }
        ]
    )

    print(response.choices[0].message.content)

