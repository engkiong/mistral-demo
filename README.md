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

## Phase 1: one-shot chat (you are here: start)

Fill in the two TODOs in `naive_chat.py`: write the prompt, then call the chat model.

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

**You are done when** the model prints an answer for a claim. Run claim_b three times.
The decision and the format change from run to run (approve, partial, reject, escalate).
`mistral-medium-latest` often gets the arithmetic right. The problem is that the answer
is not stable, and there is nothing to parse, test or retry. Phase 2 fixes that.
