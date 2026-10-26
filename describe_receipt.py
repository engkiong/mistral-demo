"""Send a receipt image to Mistral Small and print a description as JSON."""
import base64
import os
import sys

from dotenv import load_dotenv
from mistralai.client import Mistral
from mistralai.client.models import ImageURLChunk, TextChunk, UserMessage

load_dotenv()

path = sys.argv[1] if len(sys.argv) > 1 else "receipts/r0001.jpg"
image = base64.b64encode(open(path, "rb").read()).decode()

client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
response = client.chat.complete(
    model="mistral-small-latest",
    response_format={"type": "json_object"},
    messages=[
        UserMessage(
            content=[
                TextChunk(
                    text="Describe this receipt as a JSON object: "
                    "merchant, items (name, quantity, amount), tax, total."
                ),
                ImageURLChunk(image_url=f"data:image/jpeg;base64,{image}"),
            ]
        )
    ],
)
message = response.choices[0].message
assert message is not None
print(message.content)
