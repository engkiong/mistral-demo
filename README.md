# Receipt reconciliation: from one-shot chat to a durable workflow

A workshop repo. We reconcile expense claims against receipts, starting with a
fragile one-shot chat prompt and ending with OCR, structured extraction,
deterministic rules, and a retried, observable Mistral Workflow.

## Setup

Requires Python 3.11+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # then put your key in .env, or export MISTRAL_API_KEY
python check_env.py
```

`check_env.py` verifies that `MISTRAL_API_KEY` is set, the OCR endpoint
responds, and the chat endpoint responds. It exits 0 when all three pass.

**Manual step:** Studio login is browser-based, so confirm yourself that you
can sign in to your Mistral Studio workspace. Observability in this workshop
is Mistral Studio only.

## Layout

```
receipts/   12 CORD v2 receipt images (naver-clova-ix/cord-v2, test split),
            each with a committed OCR-generated .txt next to it
claims/     5 staged claims + expected_decisions.json
```

More files appear as the segments are built (`common.py`, `naive_chat.py`,
`extract.py`, `reconcile.py`, `workflow.py`, `worker.py`, `run_workflow.py`).

### Staged claims

| Claim   | Receipt  | Scenario                                              | Expected               |
| ------- | -------- | ----------------------------------------------------- | ---------------------- |
| claim_a | r0001    | Clean                                                 | approve                |
| claim_b | r0002    | Tax double-counted                                    | partial (or reject)    |
| claim_c | r0003    | Discount claimed at the pre-discount price            | partial                |
| claim_d | r0004    | Ambiguous: no merchant, no stated purpose             | escalate               |
| claim_e | r0005    | Alcohol (non-reimbursable) plus change claimed        | partial (or reject)    |

`claims/expected_decisions.json` holds, per claim, the expected decision, the
expected reimbursable amount, and expected reason keywords. Amounts are in IDR.

### Receipts

`receipts/*.txt` were generated once with `mistral-ocr-latest` and committed.
The naive chat demo reads the `.txt`; `extract.py` does live OCR on the `.jpg`.
