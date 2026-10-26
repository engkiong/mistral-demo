"""Evaluate the R6 anomaly judge on its own: precision, recall and F1 over the staged claims."""
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path

import structlog
from dotenv import load_dotenv
from mistralai.evaluations import (
    CategoricalStatistics,
    Evaluator,
    Mistral,
    Score,
    Statistic,
    System,
)

from anomaly import ANOMALY_MODEL, REASONING_EFFORT, detect_anomaly
from common import ROOT, load_claim, load_receipt_text, resolve

POSITIVE = "anomaly"


def load_dataset() -> list[dict]:
    """One record per claim, labelled from expected_decisions.json."""
    expected = json.loads(resolve("claims/expected_decisions.json").read_text())
    dataset = []
    for path in sorted((ROOT / "claims").glob("claim_*.json")):
        claim = load_claim(path)
        dataset.append({
            "claim_id": claim["claim_id"],
            "currency": claim["currency"],
            # The committed OCR text: the same input on every run, and no OCR calls
            "ocr_text": load_receipt_text(Path(claim["receipt"]).with_suffix(".txt")),
            "label": POSITIVE if expected[claim["claim_id"]]["expected_anomaly"] else "normal",
        })
    return dataset


async def judge(record: dict, system: System) -> dict:
    return await asyncio.to_thread(
        detect_anomaly,
        record["currency"],
        record["ocr_text"],
        str(system.params["model"]),
        str(system.params["reasoning_effort"]),
    )


def label(record: dict, output: dict) -> Score:
    predicted = POSITIVE if output["is_anomalous"] else "normal"
    return Score(
        value=predicted, metadata={"expected": record["label"]}, rationale="; ".join(output["reasons"])
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=ANOMALY_MODEL, help='e.g. "mistral-large-4"')
    parser.add_argument("--reasoning-effort", default=REASONING_EFFORT, help='"none" or "high"')
    args = parser.parse_args()
    load_dotenv()
    # The evaluations library logs every record at debug level; keep the terminal readable
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.INFO))

    evaluator = Evaluator(
        name="anomaly",
        scorer=label,
        statistics=[
            Statistic.precision(positive_label=POSITIVE),
            Statistic.recall(positive_label=POSITIVE),
            Statistic.f1(positive_label=POSITIVE),
        ],
    )
    run = await Mistral(api_key=os.environ["MISTRAL_API_KEY"]).evaluation.run(
        dataset=load_dataset(),
        task=judge,
        system=System(
            name="anomaly_judge",
            params={"model": args.model, "reasoning_effort": args.reasoning_effort},
        ),
        evaluators=[evaluator],
        local=True,
    )

    print(f"model: {args.model}, reasoning effort: {args.reasoning_effort}\n")
    print(f"{'claim':<9}{'expected':<10}{'predicted':<11}reasons")
    for record in run.output_records:
        row = f"{record.input_record['claim_id']:<9}{record.input_record['label']:<10}"
        generation = record.generations[0]
        if generation.error:
            print(f"{row}{'ERROR':<11}{generation.error}")
            continue
        score = generation.scores["anomaly"][0]
        print(f"{row}{score.value:<11}{score.rationale}")
    stats = run.statistics["anomaly"]
    assert isinstance(stats, CategoricalStatistics)
    assert stats.values is not None and stats.confusion_matrix is not None
    print("\n" + "  ".join(f"{value.id} {value.value:.2f}" for value in stats.values))
    matrix = stats.confusion_matrix
    print(f"confusion matrix (rows: expected, columns: predicted, order {matrix.labels}): {matrix.matrix}")


if __name__ == "__main__":
    asyncio.run(main())
