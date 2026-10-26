"""Extract typed receipt fields in one OCR call, using a pydantic annotation format."""
import argparse

from mistralai.extra import response_format_from_pydantic_model
from pydantic import BaseModel, Field

from common import get_client, image_to_data_url

OCR_MODEL = "mistral-ocr-latest"

AMOUNTS = (
    "Plain number in the receipt's currency. '.' and ',' inside prices like 93.500 or "
    "93,500 are thousands separators (93500). Null if not printed; never guess or compute."
)


class Item(BaseModel):
    name: str = Field(
        description="Item name without any quantity (e.g. 'Jamur Goreng 2' -> 'Jamur Goreng')."
    )
    quantity: float | None = Field(description="Count printed next to the name or as '2 x'.")
    amount: float | None = Field(description=f"Line amount. {AMOUNTS}")


class Discount(BaseModel):
    description: str
    amount: float = Field(description="Positive number.")


class Receipt(BaseModel):
    merchant: str | None = Field(
        description="Business name, only if one is printed. A menu item is never the merchant."
    )
    items: list[Item] = Field(description="Line items as printed.")
    subtotal: float | None = Field(description=f"Subtotal before tax and discounts. {AMOUNTS}")
    tax: float | None = Field(
        description=f"Tax/VAT/PB1 only; a service charge is not tax. {AMOUNTS}"
    )
    discounts: list[Discount] = Field(description="Discount lines as printed.")
    total_paid: float | None = Field(
        description="Final amount due after tax and discounts. A second, larger 'Total'/'Cash' "
        f"line followed by a change line is the cash tendered, not this. {AMOUNTS}"
    )
    payment_method: str | None = Field(
        description="'cash' only when cash tendered or change is printed, else what is printed."
    )
    change: float | None = Field(description=f"Cash returned to the customer. {AMOUNTS}")


def extract_receipt(path: str) -> dict:
    resp = get_client().ocr.process(
        model=OCR_MODEL,
        document={"type": "image_url", "image_url": image_to_data_url(path)},
        document_annotation_format=response_format_from_pydantic_model(Receipt),
    )
    annotation = resp.document_annotation
    if not isinstance(annotation, str):
        raise ValueError("OCR returned no document annotation")
    # model_validate_json raises if any required field is missing or mistyped
    fields = Receipt.model_validate_json(annotation).model_dump()
    # Keep the raw text too: the anomaly check (R6) needs details the typed fields drop, e.g. "x40pax"
    return {**fields, "ocr_text": "\n\n".join(page.markdown for page in resp.pages)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True, help="path to a receipt .jpg")
    args = parser.parse_args()
    extraction = extract_receipt(args.receipt)
    print(Receipt.model_validate(extraction).model_dump_json(indent=2))
    print(f"\nOCR text:\n{extraction['ocr_text']}")


if __name__ == "__main__":
    main()
