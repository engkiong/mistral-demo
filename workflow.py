"""Durable claim reconciliation: the same pipeline as reconcile.py, as a retried Workflow."""
import asyncio
from datetime import timedelta
from typing import cast

import mistralai.workflows as workflows
import structlog
from temporalio import activity as temporal_activity

# Our own modules pull in the Mistral client; load them outside the determinism sandbox.
with workflows.workflow.unsafe.imports_passed_through():
    from anomaly import detect_anomaly
    from common import Claim
    from extract import extract_receipt
    from reconcile import reconcile

WORKFLOW_NAME = "claim_reconciliation_workflow"
logger = structlog.get_logger(__name__)


# Demo: the first extraction for claim_c's receipt fails once, so the retry shows in Studio.
# Process-level flag: the retry runs in the same worker process, so it then succeeds.
SEEDED_FAILURE_RECEIPT = "receipts/r0003.jpg"
_seeded_failure_fired = False


@workflows.activity(
    start_to_close_timeout=timedelta(minutes=2),
    retry_policy_max_attempts=3,
)
async def extract_activity(receipt_path: str) -> dict:
    """OCR the receipt image and extract typed fields in one call."""
    global _seeded_failure_fired
    attempt = temporal_activity.info().attempt
    logger.info("extract_activity attempt", receipt=receipt_path, attempt=attempt)
    if receipt_path == SEEDED_FAILURE_RECEIPT and not _seeded_failure_fired:
        _seeded_failure_fired = True
        logger.warning("extract_activity attempt failed, will retry", receipt=receipt_path, attempt=attempt)
        raise ConnectionError("simulated OCR outage (seeded demo failure)")
    return await asyncio.to_thread(extract_receipt, receipt_path)


@workflows.activity(
    start_to_close_timeout=timedelta(minutes=2),
    retry_policy_max_attempts=3,
)
async def anomaly_activity(claim: dict, extraction: dict) -> dict:
    """Ask the chat model whether any item or price is implausible (input to R6)."""
    return await asyncio.to_thread(detect_anomaly, claim["currency"], extraction["ocr_text"])


@workflows.activity(
    start_to_close_timeout=timedelta(minutes=2),
    retry_policy_max_attempts=3,
)
async def reconcile_activity(claim: dict, extraction: dict, anomaly: dict) -> dict:
    """Apply the deterministic rules R1-R6."""
    return reconcile(cast(Claim, claim), extraction, anomaly)


@workflows.workflow.define(name=WORKFLOW_NAME)
class ClaimReconciliationWorkflow:
    @workflows.workflow.entrypoint
    async def run(self, claim: dict) -> dict:
        extraction = await extract_activity(claim["receipt"])
        anomaly = await anomaly_activity(claim, extraction)
        result = await reconcile_activity(claim, extraction, anomaly)
        return {"claim_id": claim["claim_id"], **result}
