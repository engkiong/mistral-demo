"""Deterministic reconciliation: code decides, the model only reads the receipt."""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher

from anomaly import detect_anomaly
from common import ROOT, Claim, load_claim, resolve
from extract import extract_receipt

EXTRACTION_FIELDS = (
    "merchant", "items", "subtotal", "tax", "discounts", "total_paid", "payment_method", "change",
)
ABS_TOLERANCE = 0.02
REL_TOLERANCE = 0.01
NAME_MATCH_RATIO = 0.6

# R5 policy: only business meals and drinks are reimbursable; alcohol is not.
NON_REIMBURSABLE_KEYWORDS = (
    "alcohol", "beer", "bir ", "wine", "soju", "makoli", "makgeolli", "vodka", "whisky",
    "whiskey", "sake", "cocktail", "bintang", "heineken",
)


def close(a: float, b: float) -> bool:
    return abs(a - b) <= max(ABS_TOLERANCE, REL_TOLERANCE * max(abs(a), abs(b)))


def fmt(amount: float) -> str:
    return f"{amount:,.0f}"


def is_non_reimbursable(name: str) -> bool:
    name = f"{name.lower()} "
    return any(keyword in name for keyword in NON_REIMBURSABLE_KEYWORDS)


def match_items(claim_items: list[dict], receipt_items: list[dict]) -> list[tuple[dict, dict | None]]:
    """Greedy one-to-one assignment of claim items to receipt items by name similarity."""
    pairs = sorted(
        (
            (SequenceMatcher(None, c["name"].lower(), r["name"].lower()).ratio(), ci, ri)
            for ci, c in enumerate(claim_items)
            for ri, r in enumerate(receipt_items)
        ),
        reverse=True,
    )
    assigned: dict[int, int] = {}
    used: set[int] = set()
    for ratio, ci, ri in pairs:
        if ratio >= NAME_MATCH_RATIO and ci not in assigned and ri not in used:
            assigned[ci] = ri
            used.add(ri)
    return [(c, receipt_items[assigned[i]] if i in assigned else None) for i, c in enumerate(claim_items)]


def check_escalation(claim: Claim, receipt: dict) -> list[str]:
    """R4: critical fields missing, or an item-level mismatch beyond tolerance."""
    reasons = []
    if receipt["total_paid"] is None:
        reasons.append("R4: receipt total is missing")
    if not receipt["items"]:
        reasons.append("R4: receipt has no readable line items")
    elif not claim["items"]:
        reasons.append("R4: claim has no line items")
    else:
        for claimed, found in match_items(claim["items"], receipt["items"]):
            if found is None:
                reasons.append(f"R4: item mismatch: '{claimed['name']}' not found on receipt")
            elif found["amount"] is not None and not close(claimed["amount"], found["amount"]):
                reasons.append(
                    f"R4: item mismatch: '{claimed['name']}' claimed {fmt(claimed['amount'])}, "
                    f"receipt shows {fmt(found['amount'])}"
                )
    return reasons


def check_tax_once(claim: Claim, receipt: dict) -> tuple[list[str], float]:
    """R2: tax counted once. Returns (reasons, amount of excess the tax overclaim explains)."""
    receipt_tax = receipt["tax"] or 0
    if claim["tax_claimed"] > receipt_tax and not close(claim["tax_claimed"], receipt_tax):
        twice = receipt_tax > 0 and close(claim["tax_claimed"], 2 * receipt_tax)
        how = "counted twice" if twice else "overstated"
        reason = f"R2: tax {how}: claimed {fmt(claim['tax_claimed'])}, receipt shows {fmt(receipt_tax)}"
        return [reason], claim["tax_claimed"] - receipt_tax
    return [], 0.0


def check_anomaly(anomaly: dict | None) -> list[str]:
    """R6: the model judged an item or price implausible for a business meal."""
    if not anomaly or not anomaly["is_anomalous"]:
        return []
    return [f"R6: anomaly: {reason}" for reason in anomaly["reasons"]] or ["R6: anomaly flagged"]


def reconcile(claim: Claim, receipt: dict, anomaly: dict | None = None) -> dict:
    """Apply R1-R6 and return {decision, reasons, reimbursable_amount}."""
    # R4 before R6: a claim a human must review anyway is escalated, with the anomaly noted
    escalation = check_escalation(claim, receipt)
    anomalies = check_anomaly(anomaly)
    if escalation:
        return {"decision": "escalate", "reasons": escalation + anomalies, "reimbursable_amount": 0}
    if anomalies:
        return {"decision": "reject", "reasons": anomalies, "reimbursable_amount": 0}

    claimed = claim["claimed_total"]
    total = receipt["total_paid"]
    reasons: list[str] = []
    explained_excess = 0.0

    tax_reasons, tax_excess = check_tax_once(claim, receipt)
    reasons += tax_reasons
    explained_excess += tax_excess

    # R3: discounts at the post-discount price
    discount = sum(d["amount"] for d in receipt["discounts"])
    if discount > ABS_TOLERANCE and claim["discount_claimed"] < discount and not close(claim["discount_claimed"], discount):
        missing = discount - claim["discount_claimed"]
        reasons.append(
            f"R3: discount of {fmt(discount)} not applied: claim uses the pre-discount price"
        )
        explained_excess += missing

    # R5: change is not claimable; whatever excess R2/R3 don't explain is change
    residual = claimed - total - explained_excess
    if residual > max(ABS_TOLERANCE, REL_TOLERANCE * total):
        reasons.append(
            f"R5: change not claimable: claimed total exceeds the receipt total by {fmt(residual)}"
        )

    # R5: non-reimbursable items, with their pro-rata share of tax/service removed
    reimbursable = min(claimed, total)
    excluded = [item for item in claim["items"] if is_non_reimbursable(item["name"])]
    if excluded:
        base = receipt["subtotal"] or sum(i["amount"] or 0 for i in receipt["items"])
        excluded_amount = sum(item["amount"] for item in excluded)
        reimbursable = round(reimbursable * (base - excluded_amount) / base, 2)
        names = ", ".join(f"{item['name']} ({fmt(item['amount'])})" for item in excluded)
        reasons.append(f"R5: alcohol / non-reimbursable items excluded: {names}")

    # R1: totals match within tolerance
    if not reasons:
        if close(claimed, total):
            reasons.append(f"R1: claimed total matches receipt total {fmt(total)}")
        else:
            reasons.append(
                f"R1: claimed total {fmt(claimed)} is below receipt total {fmt(total)}; "
                "reimbursing the claimed amount"
            )

    if reimbursable <= 0:
        decision = "reject"
    elif reasons[0].startswith("R1"):
        decision = "approve"
    else:
        decision = "partial"
    return {"decision": decision, "reasons": reasons, "reimbursable_amount": reimbursable}


def reconcile_claim(path: str) -> tuple[Claim, dict]:
    claim = load_claim(path)
    extraction = extract_receipt(claim["receipt"])
    anomaly = detect_anomaly(claim["currency"], extraction["ocr_text"])
    result = reconcile(claim, extraction, anomaly)
    missing = [field for field in EXTRACTION_FIELDS if field not in extraction]
    if missing:
        result["warnings"] = [f"extraction is missing fields {missing} (see the TODO in extract.py)"]
    return claim, result


def reconcile_claim_safely(path: str) -> tuple[Claim, dict]:
    """Like reconcile_claim, but a crashing claim becomes a FAIL line instead of aborting the run."""
    try:
        return reconcile_claim(path)
    except Exception as exc:
        reasons = [f"crashed: {type(exc).__name__}: {exc} (a rule may be an unimplemented TODO)"]
        return load_claim(path), {"decision": "error", "reasons": reasons, "reimbursable_amount": 0}


def check_against_expected(claim_id: str, result: dict, expected: dict) -> list[str]:
    """Return the list of failed expectations (empty means PASS)."""
    problems = []
    if result["decision"] not in expected["acceptable_decisions"]:
        problems.append(f"decision {result['decision']} not in {expected['acceptable_decisions']}")
    if not close(result["reimbursable_amount"], expected["expected_reimbursable_amount"]):
        problems.append(
            f"amount {fmt(result['reimbursable_amount'])} != {fmt(expected['expected_reimbursable_amount'])}"
        )
    text = " ".join(result["reasons"]).lower()
    missing = [k for k in expected["expected_reason_keywords"] if k.lower() not in text]
    if missing:
        problems.append(f"reason keywords missing: {missing}")
    return problems


def run_all() -> int:
    paths = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "claims").glob("claim_*.json"))
    expected = json.loads(resolve("claims/expected_decisions.json").read_text())
    with ThreadPoolExecutor() as pool:
        outcomes = list(pool.map(reconcile_claim_safely, paths))

    print(f"{'claim':<9}{'decision':<10}{'amount':>12}  {'result':<6} reasons")
    passed = 0
    for claim, result in outcomes:
        problems = check_against_expected(claim["claim_id"], result, expected[claim["claim_id"]])
        passed += not problems
        status = "PASS" if not problems else "FAIL"
        print(
            f"{claim['claim_id']:<9}{result['decision']:<10}{fmt(result['reimbursable_amount']):>12}  "
            f"{status:<6} {'; '.join(result['reasons'])}"
        )
        for problem in problems:
            print(f"{'':<39}-> {problem}")
        for warning in result.get("warnings", []):
            print(f"{'':<39}!! {warning}")
    print(f"\n{passed}/{len(outcomes)} PASS")
    return 0 if passed == len(outcomes) else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="run all staged claims and compare")
    group.add_argument("--claim", help="path to one claim JSON file")
    args = parser.parse_args()
    if args.all:
        sys.exit(run_all())
    claim, result = reconcile_claim(args.claim)
    print(json.dumps({"claim_id": claim["claim_id"], **result}, indent=2))


if __name__ == "__main__":
    main()
