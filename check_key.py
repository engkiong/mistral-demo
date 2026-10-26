"""Check that your Mistral API key works."""
import os

from dotenv import load_dotenv
from mistralai.client import Mistral

load_dotenv()

client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
response = client.chat.complete(
    model="mistral-small-latest",
    messages=[{"role": "user", "content": "Reply with the single word: ok"}],
)
print(response.choices[0].message.content)
print("Your key works.")
