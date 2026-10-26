# Receipts

A small, rough repo for the workshop. We will make it better together.

## Setup

Python 3.12+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # put your Mistral API key in .env
```

Already use [uv](https://docs.astral.sh/uv/)? Use it instead of `venv` and `pip`:

```bash
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env    # put your Mistral API key in .env
```

After this, every `python ...` command below works the same. Or skip the venv and let uv
make a throwaway environment for each run:

```bash
uv run --with-requirements requirements.txt check_key.py
```

No Python and no uv? Install uv first. It then downloads Python 3.12 for you:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh      # macOS and Linux; open a new terminal after
# Windows (PowerShell): powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv venv --python 3.12 && source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
cp .env.example .env    # put your Mistral API key in .env
```

## Scripts

```bash
python check_key.py                          # does my key work?
python describe_receipt.py receipts/r0001.jpg   # receipt image -> JSON
```

`receipts/` has three receipt images to try.

## Next: the workshop

The workshop has four phases. Each phase has a start branch (with gaps to fill in)
and an end branch (the gaps filled in):

| Phase | You build                              | Start branch     | End branch     |
| ----- | -------------------------------------- | ---------------- | -------------- |
| 1     | One-shot chat on an expense claim      | `phase-1-start`  | `phase-1-end`  |
| 2     | Typed extraction and rules             | `phase-2-start`  | `phase-2-end`  |
| 3     | A durable workflow with retries        | `phase-3-start`  | `phase-3-end`  |
| 4     | A model judge and its evaluation       | `phase-4-start`  | `phase-4-end`  |

Begin with `git checkout phase-1-start`. To skip ahead, check out the `end` branch of the
phase before. The full solution is on the `solution` branch.
