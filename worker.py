"""Local worker: runs the workflow and its activities, polling Mistral's hosted orchestrator."""
import asyncio
import os

from dotenv import load_dotenv

load_dotenv()  # before importing the SDK, which reads its config from the environment
os.environ.setdefault("DEPLOYMENT_NAME", "claims-reconciliation")  # override in .env per machine

import mistralai.workflows as workflows  # noqa: E402

from workflow import ClaimReconciliationWorkflow  # noqa: E402  (importing registers the activities)


async def main() -> None:
    await workflows.run_worker([ClaimReconciliationWorkflow])


if __name__ == "__main__":
    asyncio.run(main())
