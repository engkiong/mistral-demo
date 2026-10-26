"""One-shot baseline: ask the chat model to reconcile a claim in a single prompt."""
import argparse
import json
from pathlib import Path

from mistralai.client.models import UserMessage

from common import DECISION_LABELS, Claim, get_client, load_claim, load_receipt_text

CHAT_MODEL = "mistral-medium-latest"


def build_prompt(claim: Claim, receipt_text: str) -> str:
    # TODO: write one prompt that tells the model to act as an expense auditor, gives it the
    #       claim (as JSON) and the receipt text, and asks for one of DECISION_LABELS.
    raise NotImplementedError("write the prompt")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claim", required=True, help="path to a claim JSON file")
    args = parser.parse_args()

    claim = load_claim(args.claim)
    receipt_text = load_receipt_text(Path(claim["receipt"]).with_suffix(".txt"))
    # TODO: send build_prompt(claim, receipt_text) with get_client().chat.complete(...) and print
    #       the reply. Keep it simple: no parsing, no tools, no temperature setting.
    raise NotImplementedError("call the chat model")


if __name__ == "__main__":
    main()
