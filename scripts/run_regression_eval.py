from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from apps.api.core.container import get_container
from apps.api.domain.models import Classification, Document, EvaluationCase


class RegressionGateError(RuntimeError):
    pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic Agent regression evaluation.")
    parser.add_argument(
        "--dataset",
        default="data/evaluation/regression_ko.json",
        help="Path to evaluation dataset JSON.",
    )
    parser.add_argument(
        "--sample-docs",
        default="data/sample_docs",
        help="Directory containing markdown documents to ingest before evaluation.",
    )
    args = parser.parse_args()

    dataset = _load_json(Path(args.dataset))
    container = get_container()
    tenant_id = str(dataset.get("tenant_id", "default"))

    _ingest_sample_docs(container=container, tenant_id=tenant_id, sample_dir=Path(args.sample_docs))
    cases = [
        EvaluationCase(
            tenant_id=tenant_id,
            evaluation_run_id=_zero_uuid(),
            input_query=str(item["input_query"]),
            expected_facts=[str(fact) for fact in item.get("expected_facts", [])],
        )
        for item in _required_list(dataset, "cases")
    ]

    run = container.evaluate_agent.execute(
        tenant_id=tenant_id,
        name=str(dataset.get("name", "regression")),
        scenario=str(dataset.get("scenario", "operations")),
        cases=cases,
        actor_id="regression-gate",
    )

    minimum_average_score = float(dataset.get("minimum_average_score", 0.8))
    minimum_pass_rate = float(dataset.get("minimum_pass_rate", 1.0))
    average_score = float(run.metrics["average_score"])
    pass_rate = float(run.metrics["pass_rate"])

    print(json.dumps(_summary(run), ensure_ascii=False, indent=2, sort_keys=True))

    failures: list[str] = []
    if average_score < minimum_average_score:
        failures.append(
            f"average_score {average_score} is below minimum {minimum_average_score}"
        )
    if pass_rate < minimum_pass_rate:
        failures.append(f"pass_rate {pass_rate} is below minimum {minimum_pass_rate}")
    failed_cases = [case for case in run.cases if case.failure_reason]
    if failed_cases:
        failures.extend(f"{case.input_query}: {case.failure_reason}" for case in failed_cases)

    if failures:
        raise RegressionGateError("; ".join(failures))


def _ingest_sample_docs(*, container: Any, tenant_id: str, sample_dir: Path) -> None:
    for path in sorted(sample_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        title = content.splitlines()[0].removeprefix("# ").strip()
        document = Document(
            tenant_id=tenant_id,
            title=title,
            content=content,
            source_type="manual",
            source_uri=str(path),
            classification=Classification.INTERNAL,
            metadata={"domain": "enterprise-ax", "language": "ko", "seed": "regression"},
        )
        container.ingest_document.execute(document=document, actor_id="regression-gate")


def _summary(run: Any) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "name": run.name,
        "scenario": run.scenario,
        "status": run.status.value,
        "metrics": run.metrics,
        "cases": [
            {
                "input_query": case.input_query,
                "score": case.score,
                "failure_reason": case.failure_reason,
            }
            for case in run.cases
        ],
    }


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("dataset root must be a JSON object")
    return data


def _required_list(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = data.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{key} must be a non-empty list")
    return [item for item in value if isinstance(item, dict)]


def _zero_uuid() -> Any:
    from uuid import UUID

    return UUID("00000000-0000-0000-0000-000000000000")


if __name__ == "__main__":
    main()
