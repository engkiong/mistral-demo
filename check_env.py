"""Verify the workshop environment: API key, OCR endpoint, chat endpoint."""
import base64
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mistralai.client import Mistral

OCR_MODEL = "mistral-ocr-latest"
CHAT_MODEL = "mistral-small-latest"
SAMPLE_RECEIPT = Path(__file__).parent / "receipts" / "r0001.jpg"


def check_api_key() -> Mistral:
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        raise RuntimeError("MISTRAL_API_KEY is not set (see .env.example)")
    return Mistral(api_key=key)


def check_ocr(client: Mistral) -> None:
    data = base64.b64encode(SAMPLE_RECEIPT.read_bytes()).decode()
    resp = client.ocr.process(
        model=OCR_MODEL,
        document={"type": "image_url", "image_url": f"data:image/jpeg;base64,{data}"},
    )
    if not resp.pages or not resp.pages[0].markdown.strip():
        raise RuntimeError("OCR returned no text")


def check_chat(client: Mistral) -> None:
    resp = client.chat.complete(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": "Reply with the single word: ok"}],
        max_tokens=5,
    )
    if not resp.choices:
        raise RuntimeError("chat returned no choices")


def main() -> int:
    load_dotenv()
    failures = 0
    try:
        client = check_api_key()
        print("OK    MISTRAL_API_KEY present")
    except RuntimeError as exc:
        print(f"FAIL  MISTRAL_API_KEY present: {exc}")
        return 1
    for label, check in [
        ("OCR endpoint responds", check_ocr),
        ("Chat endpoint responds", check_chat),
    ]:
        try:
            check(client)
            print(f"OK    {label}")
        except Exception as exc:  # report every check, don't stop at the first
            failures += 1
            print(f"FAIL  {label}: {exc}")
    print("\nReminder: confirm manually that you can log in to your Mistral Studio workspace.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
