"""One-shot baseline: ask the chat model to reconcile a claim in a single prompt."""
import argparse
import json
from pathlib import Path

from mistralai.client.models import UserMessage

from common import DECISION_LABELS, Claim, get_client, load_claim, load_receipt_text

CHAT_MODEL = "mistral-medium-latest"


def build_prompt(claim: Claim, receipt_text: str) -> str:
    return (
        "You are an expense auditor. Reconcile the expense claim below against the "
        "receipt text and decide whether to reimburse it.\n"
        f"Decision options: {', '.join(DECISION_LABELS)}.\n\n"
        f"CLAIM (JSON):\n{json.dumps(claim, indent=2)}\n\n"
        f"RECEIPT (OCR text):\n{receipt_text}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claim", required=True, help="path to a claim JSON file")
    args = parser.parse_args()

    claim = load_claim(args.claim)
    receipt_text = load_receipt_text(Path(claim["receipt"]).with_suffix(".txt"))
    # No parsing, no tools, no temperature override: sampling stays on on purpose.
    resp = get_client().chat.complete(
        model=CHAT_MODEL,
        messages=[UserMessage(content=build_prompt(claim, receipt_text))],
    )
    message = resp.choices[0].message
    assert message is not None
    print(message.content)


if __name__ == "__main__":
    main()
