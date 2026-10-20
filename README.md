# Receipt reconciliation: from one-shot chat to a durable workflow

A workshop repo. We reconcile expense claims against receipts, starting with a
fragile one-shot chat prompt and ending with OCR, structured extraction,
deterministic rules, and a retried, observable Mistral Workflow.

## Setup

Requires Python 3.12+ (the Workflows SDK needs it).

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
| claim_d | r0004    | Ambiguous: no purpose, items mismatch receipt           | escalate               |
| claim_e | r0005    | Alcohol (non-reimbursable) plus change claimed        | partial (or reject)    |

`claims/expected_decisions.json` holds, per claim, the expected decision, the
expected reimbursable amount, and expected reason keywords. Amounts are in IDR.

### The one-shot baseline

```bash
python naive_chat.py --claim claims/claim_a.json
python naive_chat.py --claim claims/claim_b.json   # run it a few times
```

One prompt, one sampled completion, raw text out. Don't expect a single
dramatic failure: `mistral-small-latest` often does the arithmetic right. What
you will see is that the answer, the decision and even the output format change
from run to run (approve / partial / reject / escalate). At scale, inconsistent
is wrong, and there is nothing to parse, test or retry.

### The durable workflow

`workflow.py` runs the same pipeline as a Mistral Workflow: `extract_activity`
(one OCR call with the receipt schema) then `reconcile_activity` (rules R1-R5),
each with a 2-minute start-to-close timeout and up to 3 attempts. The
orchestrator is Mistral-hosted; the worker runs on your machine.

```bash
python worker.py &              # registers the workflow + activities and polls for work
python run_workflow.py --all    # one execution per claim; prints IDs, waits for results
```

Watch the executions in Mistral Studio: Workflows > `claim_reconciliation_workflow`
> Executions (https://console.mistral.ai/build/workflows). Use an API key from the
same workspace you are looking at. The worker needs a `DEPLOYMENT_NAME`; it
defaults to `claims-reconciliation`. Set the variable in your environment if
several people share a workspace.

**Retry demo:** `extract_activity` fails once, on the first attempt for claim_c's
receipt (`r0003.jpg`), with a simulated OCR outage. The retry policy reruns it
and it succeeds, so the claim_c execution shows one failed and one succeeded
attempt and ends green. The failure flag lives in the worker process: restart
`worker.py` before each run to make it fail again.

### Receipts

`receipts/*.txt` were generated once with `mistral-ocr-latest` and committed.
The naive chat demo reads the `.txt`; `extract.py` does live OCR on the `.jpg`.
