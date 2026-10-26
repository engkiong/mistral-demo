"""Check that your Mistral API key works."""
import os

from dotenv import load_dotenv
from mistralai.client import Mistral
from mistralai.client.models import UserMessage

load_dotenv()

client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
response = client.chat.complete(
    model="mistral-small-latest",
    messages=[UserMessage(content="Reply with the single word: ok")],
)
message = response.choices[0].message
assert message is not None
print(message.content)
print("Your key works.")
