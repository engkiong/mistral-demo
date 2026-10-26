# Receipt reconciliation: from one-shot chat to a durable workflow

A one-hour workshop. We check expense claims against receipts. We start with one
chat prompt and end with typed extraction, deterministic rules, a model judge
and a retried Mistral Workflow.

## How the branches work

There are four phases. Each phase has a `start` and an `end` branch.

- `phase-N-start`: the code has gaps. Search for `TODO` and fill them in.
- `phase-N-end`: the gaps are filled. Switch to it if you want to skip the exercise.
- `phase-N-end` is also the base of `phase-(N+1)-start`. You can join at any phase.

| Phase | You build                                    | Branches                         |
| ----- | -------------------------------------------- | -------------------------------- |
| 1     | One-shot chat on a claim                     | `phase-1-start`, `phase-1-end`   |
| 2     | Typed extraction and rules R1-R5             | `phase-2-start`, `phase-2-end`   |
| 3     | A durable workflow with a retry policy       | `phase-3-start`, `phase-3-end`   |
| 4     | A model judge (R6) and its evaluation        | `phase-4-start`, `phase-4-end`   |

Switch with `git checkout phase-2-start`. Commit or stash your work first.

`main` is the small starter: `check_key.py` and `describe_receipt.py`.

## Setup

Python 3.12+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # put your Mistral API key in .env
python check_key.py
```

`requirements.txt` grows with the phases. Run `pip install -r requirements.txt` again
after you switch branch.

## Data

```
receipts/   r0001-r0012: CORD v2 receipt images (naver-clova-ix/cord-v2, test split)
            r0013-r0016: generated receipts with planted anomalies
            each .jpg has an OCR text file (.txt) next to it
claims/     9 staged claims, claim_a.json to claim_i.json
```

Each claim has `claim_id`, `employee`, `submitted_on`, `currency`, `receipt` (path to
the `.jpg`), `items` (`{name, quantity, amount}`), `tax_claimed`, `discount_claimed`,
`claimed_total` and `notes`. All amounts are in IDR. Every claim is for a business meal.

| Claim   | Receipt | Scenario                                         | Right decision       |
| ------- | ------- | ------------------------------------------------ | -------------------- |
| claim_a | r0001   | Clean                                            | approve              |
| claim_b | r0002   | Tax double-counted                               | partial              |
| claim_c | r0003   | Discount claimed at the pre-discount price       | partial              |
| claim_d | r0004   | Items do not match the receipt                   | escalate             |
| claim_e | r0005   | Alcohol, plus change claimed                     | partial              |
| claim_f | r0013   | GPU hours and a "Devstral sprint"                | reject               |
| claim_g | r0014   | Dinner for 40 people for 40,000                  | reject               |
| claim_h | r0015   | Wedding ring and PlayStation 5                   | reject               |
| claim_i | r0016   | 10 cats, 200 baguettes for 17,000                | reject               |

## Phase 1: one-shot chat (done)

`naive_chat.py` is finished: it builds one prompt and prints the raw reply.

**What the prompt must do.** Act as an expense auditor and give one decision from
`DECISION_LABELS`. Apply these five rules (phase 2 turns them into code):

| Rule | The model checks that                                                              |
| ---- | ---------------------------------------------------------------------------------- |
| R1   | The claimed total matches the receipt total (within about 1%).                     |
| R2   | Tax is counted once.                                                               |
| R3   | A discount is applied: the claim uses the post-discount price.                     |
| R4   | Every claimed item is on the receipt with the same amount. If not, escalate.       |
| R5   | Change and alcohol are not claimed. Only the rest is reimbursed (partial).         |

| Decision   | Use it when                                          | Reimburse             |
| ---------- | ---------------------------------------------------- | --------------------- |
| `approve`  | The claim matches the receipt                        | The claimed total     |
| `partial`  | Part of the claim is not allowed (R2, R3, R5)        | A lower amount        |
| `reject`   | Nothing in the claim is allowed                      | 0                     |
| `escalate` | Receipt and claim do not match (R4): a human checks  | 0                     |

Two things on the receipts: `.` and `,` inside a price are thousands separators
(`93.500` is 93,500). A receipt may print a second, larger "Total" or "Cash" line, then a
change line ("Kembali"). That is the cash handed over, not the bill. Compare the claim with
the bill (the amount due after tax and discounts).

Rule R6 (items that are not a meal) is not part of this phase. Phase 4 adds it.

```bash
python naive_chat.py --claim claims/claim_a.json
python naive_chat.py --claim claims/claim_b.json   # run it a few times
```

Run claim_b three times.
The decision and the format change from run to run (approve, partial, reject, escalate).
`mistral-medium-latest` often gets the arithmetic right. The problem is that the answer
is not stable, and there is nothing to parse, test or retry. Phase 2 fixes that.

## Phase 2: typed extraction and rules (done)

Two ideas: the model only *reads* the receipt into typed fields, and plain code
*decides*. Setup: run `pip install -r requirements.txt` again.

These gaps are filled in:

| File           | TODO                                                                  |
| -------------- | --------------------------------------------------------------------- |
| `extract.py`   | add the `payment_method` and `change` fields to the `Receipt` schema  |
| `reconcile.py` | implement R2 (`check_tax_once`) and R4 (`check_escalation`)           |

```bash
python extract.py --receipt receipts/r0001.jpg   # one OCR call, typed JSON out
python reconcile.py --all                        # extraction + rules over claims a to e
```

**Check it:**

1. `extract.py --receipt receipts/r0001.jpg` prints `"payment_method": "cash"` and
   `"change": 6500`. Until then, `reconcile.py --all` prints a `!!` warning under each claim.
2. `reconcile.py --all` prints **5/5 PASS**. Before the fix it is **3/5**: claim_b fails
   (no R2) and claim_d fails (no R4, so it is not escalated).

`reconcile.py --all` skips claim_f to claim_i. A rule cannot catch them. The model judge
(R6) does, in phase 4.

The rules: R1 the totals match. R2 tax is counted once. R3 discounts use the post-discount
price. R4 escalate to a human when the receipt and claim do not match. R5 change and
alcohol are not claimable.

## Phase 3: a durable workflow (done)

`workflow.py` runs the same pipeline as a Mistral Workflow: `extract_activity` (one OCR
call), then `reconcile_activity` (rules R1-R5). The orchestrator is hosted by Mistral.
The worker runs on your machine. Setup: run `pip install -r requirements.txt` again.

This gap is filled in:

| File          | TODO                                                                |
| ------------- | ------------------------------------------------------------------- |
| `workflow.py` | give `extract_activity` its retry policy (2 min timeout, 3 attempts) |

`extract_activity` fails once on claim_c's receipt (`r0003.jpg`), with a simulated OCR
outage. This is on purpose. With one attempt, the claim fails. With a retry policy, it recovers.

```bash
python worker.py &                                    # registers the workflow, polls for work
python run_workflow.py --claim claims/claim_c.json    # one execution, waits for the result
```

**Check it:** the claim_c execution ends **COMPLETED**, and the worker log shows
`attempt=1` failing, then `attempt=2`. Before the fix it ends **FAILED**.

- The failure flag lives in the worker process. Restart the worker before each run.
- The worker needs a `DEPLOYMENT_NAME`. It defaults to `claims-reconciliation`. Set the
  variable in your environment if several people share a workspace.
- Stop the worker by its PID (`kill %1`), not with `pkill -f`: that can hit other people's workers.
- Watch the runs in Mistral Studio: Workflows > `claim_reconciliation_workflow` > Executions
  (https://console.mistral.ai/build/workflows). Use a key from the same workspace.
  Studio does not mark the failed attempt. The worker terminal does.
- Manual step: confirm you can sign in to your Mistral Studio workspace.

## Phase 4: a model judge and its evaluation (you are here: end)

R6 is the one rule a model decides: it flags items that are not food or drink, and prices
that are implausible for what was bought. The judge is in `anomaly.py`. It now runs in
`reconcile.py` and in the workflow (`anomaly_activity`). Setup: run `pip install -r requirements.txt`
again.

This gap is filled in:

| File         | TODO                                                                           |
| ------------ | ------------------------------------------------------------------------------ |
| `anomaly.py` | write `INSTRUCTIONS`: what is an anomaly, and what is not (other rules handle it) |

`evaluate.py` runs the judge on the committed OCR text of every claim. It compares each verdict
with `expected_anomaly` in `claims/expected_decisions.json`, and prints precision, recall, F1
and a confusion matrix (positive label: `anomaly`). Nothing is uploaded.

```bash
python evaluate.py                                # the judge on its own
python reconcile.py --all                         # the whole rule set, now with R6
python evaluate.py --reasoning-effort none        # try other settings
python evaluate.py --model mistral-large-4
```

**Check it:** `evaluate.py` catches all five anomalies and flags none of the four
clean claims (precision and recall both near 1.00). The starter prompt scores about precision
0.71: it flags the clean receipt and the alcohol claim.

Then run `reconcile.py --all`. It should print **9/9 PASS** most of the time. A live run can
still fail one claim: OCR may read an item name differently (so R4 escalates before R6 runs), or
a call may time out. Run each setting more than once before you compare. A model can judge,
but the decision stays in rules you can test.

The finished prompt in `anomaly.py` is short. It treats every claim as a meal for one person or
a group of up to 4, and flags three things: an item that is not food or drink, more than 4
people served, and a price that is not reasonable per person (about 10 times off, with a normal
range in IDR). A vaguer prompt flagged clean claims (cheap fried mushrooms, a 61,000 coffee).
Giving the normal range and the "10 times" rule fixed that. The 40-guest dinner is caught by
the group-size rule.

Five claims are anomalies: claim_f to claim_i, and claim_d (a CORD receipt for reusable lunch
boxes). R4 runs before R6, so claim_d is escalated, with the anomaly in its reasons.
