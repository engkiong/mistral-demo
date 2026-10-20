"""Shared helpers: Mistral client, claim/receipt loading, image encoding."""
import base64
import json
import mimetypes
import os
from pathlib import Path
from typing import NotRequired, TypedDict

from dotenv import load_dotenv
from mistralai.client import Mistral

ROOT = Path(__file__).parent
DECISION_LABELS = ("approve", "partial", "reject", "escalate")


class ClaimItem(TypedDict):
    name: str
    quantity: int
    amount: int


class Claim(TypedDict):
    claim_id: str
    employee: str
    submitted_on: str
    currency: str
    receipt: str  # repo-relative path to the receipt .jpg
    purpose: str | None
    items: list[ClaimItem]
    tax_claimed: int
    discount_claimed: int
    claimed_total: int
    notes: NotRequired[str]


def resolve(path: str | Path) -> Path:
    """Resolve repo-relative paths against the repo root, so cwd doesn't matter."""
    return ROOT / path  # an absolute `path` wins over ROOT


def get_client() -> Mistral:
    load_dotenv()
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        raise RuntimeError("MISTRAL_API_KEY is not set (see .env.example)")
    return Mistral(api_key=key)


def load_claim(path: str | Path) -> Claim:
    return json.loads(resolve(path).read_text())


def load_receipt_text(txt_path: str | Path) -> str:
    """Read the committed OCR text of a receipt (pass the .txt path)."""
    return resolve(txt_path).read_text()


def image_to_data_url(path: str | Path) -> str:
    path = resolve(path)
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"
