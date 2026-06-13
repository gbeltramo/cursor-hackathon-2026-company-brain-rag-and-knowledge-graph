from openai import OpenAI
import os 
import time

REGOLO_API_KEY = os.environ["REGOLO_API_KEY"]

def main():
    client = OpenAI(
        api_key=REGOLO_API_KEY,
        base_url="https://api.regolo.ai/v1"
    )

    st = time.time()
    response = client.chat.completions.create(
        model="qwen3.5-9b",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the capital of Italy?"}
        ]
    )
    et = time.time()

    print(response.choices[0].message.content)