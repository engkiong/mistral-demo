# Receipts

A small, rough repo for the workshop. We will make it better together.

## Setup

Python 3.12+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # put your Mistral API key in .env
```

## Scripts

```bash
python check_key.py                          # does my key work?
python describe_receipt.py receipts/r0001.jpg   # receipt image -> JSON
```

`receipts/` has three receipt images to try.
