"""R6 anomaly check: a chat model judges whether a receipt fits a business meal."""
import argparse
import json
from typing import cast

from mistralai.client.models import ReasoningEffort, SystemMessage, TextChunk, UserMessage
from mistralai.client.models import ReasoningEffort, TextChunk
from mistralai.extra import response_format_from_pydantic_model
from pydantic import BaseModel, Field

from common import get_client, load_claim
from extract import extract_receipt

ANOMALY_MODEL = "mistral-medium-3-5"
REASONING_EFFORT = "high"

# TODO: write the instructions. Say what IS an anomaly (what must the items and prices of a
#       business meal look like?) and what is NOT (other rules already handle alcohol, tax and
#       service charges, discounts, change, arithmetic errors, and blurred receipt details).
#       Ask for one short reason per anomalous item, and no reasons if nothing is anomalous.
#       Then run `python evaluate.py` and improve the prompt until it scores well.
INSTRUCTIONS = """\
You audit expense claims. Every claim is for a business meal. Read the receipt text and
say whether the claim is anomalous."""


class AnomalyVerdict(BaseModel):
    reasons: list[str] = Field(description="One short reason per anomalous item; empty if none.")
    is_anomalous: bool


def detect_anomaly(
    currency: str, ocr_text: str, model: str = ANOMALY_MODEL, reasoning_effort: str = REASONING_EFFORT
) -> dict:
    messages: list[SystemMessage | UserMessage] = [
        SystemMessage(content=INSTRUCTIONS),
        UserMessage(content=f"Currency: {currency}\n\nRECEIPT (OCR text):\n{ocr_text}"),
    ]
    resp = get_client().chat.complete(
        model=model,
        messages=messages,
        response_format=response_format_from_pydantic_model(AnomalyVerdict),
        reasoning_effort=cast(ReasoningEffort, reasoning_effort),
    )
    message = resp.choices[0].message
    assert message is not None
    content = message.content
    # With reasoning on, the answer follows thinking chunks, so chat.parse can't read it
    if isinstance(content, list):
        content = "".join(chunk.text for chunk in content if isinstance(chunk, TextChunk))
    if not isinstance(content, str):
        raise ValueError("the model returned no text")
    return AnomalyVerdict.model_validate_json(content).model_dump()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claim", required=True, help="path to one claim JSON file")
    parser.add_argument("--model", default=ANOMALY_MODEL)
    parser.add_argument("--reasoning-effort", default=REASONING_EFFORT, help='"none" or "high"')
    args = parser.parse_args()
    claim = load_claim(args.claim)
    ocr_text = extract_receipt(claim["receipt"])["ocr_text"]
    verdict = detect_anomaly(claim["currency"], ocr_text, args.model, args.reasoning_effort)
    print(json.dumps(verdict, indent=2))


if __name__ == "__main__":
    main()
