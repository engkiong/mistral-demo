"""Durable claim reconciliation: the same pipeline as reconcile.py, as a retried Workflow."""
import asyncio
from datetime import timedelta

import mistralai.workflows as workflows

# Our own modules pull in the Mistral client; load them outside the determinism sandbox.
with workflows.workflow.unsafe.imports_passed_through():
    from extract import extract_receipt
    from reconcile import reconcile

WORKFLOW_NAME = "claim_reconciliation_workflow"


@workflows.activity(
    start_to_close_timeout=timedelta(minutes=2),
    retry_policy_max_attempts=3,
)
async def extract_activity(receipt_path: str) -> dict:
    """OCR the receipt image and extract typed fields in one call."""
    return await asyncio.to_thread(extract_receipt, receipt_path)


@workflows.activity(
    start_to_close_timeout=timedelta(minutes=2),
    retry_policy_max_attempts=3,
)
async def reconcile_activity(claim: dict, extraction: dict) -> dict:
    """Apply the deterministic rules R1-R5."""
    return reconcile(claim, extraction)


@workflows.workflow.define(name=WORKFLOW_NAME)
class ClaimReconciliationWorkflow:
    @workflows.workflow.entrypoint
    async def run(self, claim: dict) -> dict:
        extraction = await extract_activity(claim["receipt"])
        result = await reconcile_activity(claim, extraction)
        return {"claim_id": claim["claim_id"], **result}
