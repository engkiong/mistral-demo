"""Send a receipt image to Mistral Small and print a description as JSON."""
import base64
import os
import sys

from dotenv import load_dotenv
from mistralai.client import Mistral

load_dotenv()

path = sys.argv[1] if len(sys.argv) > 1 else "receipts/r0001.jpg"
image = base64.b64encode(open(path, "rb").read()).decode()

client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
response = client.chat.complete(
    model="mistral-small-latest",
    response_format={"type": "json_object"},
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Describe this receipt as a JSON object: "
                    "merchant, items (name, quantity, amount), tax, total.",
                },
                {"type": "image_url", "image_url": f"data:image/jpeg;base64,{image}"},
            ],
        }
    ],
)
print(response.choices[0].message.content)
