"""Start one workflow execution per claim, print execution IDs, and wait for the results."""
import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from mistralai.workflows.client import get_mistral_client  # noqa: E402

from common import ROOT, load_claim  # noqa: E402
from workflow import WORKFLOW_NAME  # noqa: E402

STUDIO_URL = "https://console.mistral.ai/build/workflows"
POLL_SECONDS = 2
WAIT_SECONDS = 180
RUNNING = {"RUNNING", "CONTINUED_AS_NEW"}


async def wait_for(client, execution_id: str):
    execution = await client.workflows.executions.get_workflow_execution_async(
        execution_id=execution_id
    )
    for _ in range(WAIT_SECONDS // POLL_SECONDS):
        if str(execution.status) not in RUNNING:
            break
        await asyncio.sleep(POLL_SECONDS)
        execution = await client.workflows.executions.get_workflow_execution_async(
            execution_id=execution_id
        )
    return execution


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="one execution per staged claim")
    group.add_argument("--claim", help="path to one claim JSON file")
    parser.add_argument("--no-wait", action="store_true", help="don't poll for the results")
    args = parser.parse_args()

    paths = sorted((ROOT / "claims").glob("claim_*.json")) if args.all else [Path(args.claim)]
    client = get_mistral_client(server_url="https://api.mistral.ai", api_key=os.environ["MISTRAL_API_KEY"])

    started = []
    for path in paths:
        claim = load_claim(path)
        execution = await client.workflows.execute_workflow_async(
            workflow_identifier=WORKFLOW_NAME,
            input={"claim": claim},
        )
        started.append((claim["claim_id"], execution.execution_id))
        print(f"{claim['claim_id']}  execution_id={execution.execution_id}")
    print(f"\nStudio: {STUDIO_URL} (Workflows > {WORKFLOW_NAME} > Executions)")
    if args.no_wait:
        return

    print("\nResults:")
    finished = await asyncio.gather(*(wait_for(client, execution_id) for _, execution_id in started))
    for (claim_id, _), execution in zip(started, finished):
        result = (execution.result or {}).get("result", {})  # the API wraps the output
        print(
            f"{claim_id}  {execution.status}  {result.get('decision', '-')}  "
            f"{result.get('reimbursable_amount', '-')}"
        )


if __name__ == "__main__":
    asyncio.run(main())
