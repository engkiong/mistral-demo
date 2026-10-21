# Receipt reconciliation: from one-shot chat to a durable workflow

A workshop repo. We reconcile expense claims against receipts, starting with a
fragile one-shot chat prompt and ending with OCR, structured extraction,
deterministic rules, and a retried, observable Mistral Workflow.

## Setup

Requires **Python 3.12+** (the Workflows SDK needs it). Dependencies are pinned in
`requirements.txt`; note that `mistralai-workflows` requires `mistralai<3`, so
don't upgrade `mistralai` on its own.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # then put your key in .env, or export MISTRAL_API_KEY
python check_env.py
```

With uv instead: `uv venv --python 3.12 && uv pip install -r requirements.txt`.

`check_env.py` is the pre-flight check. It verifies that `MISTRAL_API_KEY` is set,
that `api.mistral.ai` is reachable (it fails fast with a clear message instead of
hanging), and that the OCR and chat endpoints respond. It exits 0 when all four
pass. Run it before anything else, and again before a live session.

**Manual step:** Studio login is browser-based, so confirm yourself that you
can sign in to your Mistral Studio workspace. Observability in this workshop
is Mistral Studio only.

**Troubleshooting:** if `uv` fails with `401 Unauthorized` from a private package
index, the package you need is on public PyPI. Install with a config file that
lists only PyPI (`uv --config-file <file> pip install ...`). Avoid `--no-config`:
it also drops organisation-level settings such as the proxy.

## Layout

```
receipts/   12 CORD v2 receipt images (naver-clova-ix/cord-v2, test split),
            each with a committed OCR-generated .txt next to it
claims/     5 staged claims + expected_decisions.json
```

More files appear as the segments are built (`common.py`, `naive_chat.py`,
`extract.py`, `reconcile.py`, `workflow.py`, `worker.py`, `run_workflow.py`).

### Staged claims

| Claim   | Receipt | Scenario                                         | Expected            |
| ------- | ------- | ------------------------------------------------ | ------------------- |
| claim_a | r0001   | Clean                                            | approve             |
| claim_b | r0002   | Tax double-counted                               | partial (or reject) |
| claim_c | r0003   | Discount claimed at the pre-discount price       | partial             |
| claim_d | r0004   | Ambiguous: no purpose, items mismatch receipt    | escalate            |
| claim_e | r0005   | Alcohol (non-reimbursable) plus change claimed   | partial (or reject) |

`claims/expected_decisions.json` holds, per claim, the expected decision
(`expected_decision`, plus `acceptable_decisions` where two are fine), the
expected reimbursable amount, and expected reason keywords. Amounts are in IDR.

### Claim format

Each `claims/claim_*.json` has: `claim_id`, `employee`, `submitted_on`, `currency`,
`receipt` (repo-relative path to the `.jpg`), `purpose` (may be `null`), `items`
(a list of `{name, quantity, amount}`), `tax_claimed`, `discount_claimed`,
`claimed_total`, and free-text `notes`. The `Claim` type in `common.py` is the
reference. The notes are deliberately neutral ("Paid cash."): they must never
give the answer away.

How each claim is decided, by deterministic rules in `reconcile.py`:

- **claim_a** approves: every check passes.
- **claim_b** claims 11,200 tax where the receipt shows 5,600 (rule R2).
- **claim_c** claims the pre-discount total where the receipt shows a 19,400 discount (R3).
- **claim_d** escalates (R4) because the claim has no `purpose` and its item amounts
  (post-discount) don't match the receipt's line items. Missing merchant is *not* a
  trigger: CORD receipts rarely print one, so extraction returns `merchant: null`.
- **claim_e** includes an alcohol item (MAKOLI) and claims 500,000 against a
  426,195 receipt; the excess is change and is not claimable (R5).

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

### Extraction and rules

```bash
python extract.py --receipt receipts/r0001.jpg   # one OCR call, typed JSON out
python reconcile.py --all                        # extraction + rules over 5 claims, 5/5 PASS
```

`reconcile.py --all` prints a table with PASS/FAIL per claim. A claim that crashes
shows up as a FAIL line rather than aborting the run, and if extraction is missing
fields you will see a `!!` warning under the claim.

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
several people share a workspace. Stop the worker by its PID (`kill %1` or the PID
you noted), not with `pkill -f`, which can hit other people's workers.

**Retry demo:** `extract_activity` fails once, on the first attempt for claim_c's
receipt (`r0003.jpg`), with a simulated OCR outage. The retry policy reruns it
and it succeeds, so the claim_c execution ends green (COMPLETED).

What you can and can't see:

- **Worker terminal (reliable):** every attempt logs `extract_activity attempt` with
  its attempt number. For claim_c you see `attempt=1`, then `attempt failed, will
  retry` with the traceback, then `attempt=2`.
- **Studio:** Temporal records only the final attempt in the execution history while
  retries remain, so the timeline does **not** mark the failed attempt. The trace
  data does contain two `extract_activity` spans (attempts 1 and 2), and the claim_c
  execution runs a few seconds longer than the others. Check how your Studio
  renders it before a live demo, and keep the worker terminal on screen as the
  backup.
- The failure flag lives in the worker process: restart `worker.py` before each
  run to make it fail again. A second `run_workflow.py --all` against the same
  worker will not fail.

### Receipts

`receipts/*.txt` were generated once with `mistral-ocr-latest` and committed.
The naive chat demo reads the `.txt`; `extract.py` does live OCR on the `.jpg`.
