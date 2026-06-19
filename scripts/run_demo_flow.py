from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from apps.api.core.container import get_container
from apps.api.domain.models import Classification, Document


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the local end-to-end AX Agent operating flow."
    )
    parser.add_argument("--tenant-id", default="demo", help="Tenant id for the demo flow.")
    parser.add_argument(
        "--sample-docs",
        default="data/sample_docs",
        help="Directory containing markdown documents to ingest.",
    )
    args = parser.parse_args()

    container = get_container()
    tenant_id = args.tenant_id
    actor_id = "demo-operator"

    ingested_documents = _ingest_sample_docs(
        container=container,
        tenant_id=tenant_id,
        sample_dir=Path(args.sample_docs),
        actor_id=actor_id,
    )

    primary_run = container.run_agent.execute(
        tenant_id=tenant_id,
        scenario="knowledge-operations",
        message="Agentic RAG 운영 모델에서 질문 유형과 검색 전략을 어떻게 분리하는지 정리해줘",
        user_id=actor_id,
        actor_scopes=["records:read", "workflow:request"],
    )
    container.agent_feedback.submit(
        tenant_id=tenant_id,
        run_id=primary_run.id,
        rating=5,
        outcome="accepted",
        submitted_by=actor_id,
        comment="근거 문서와 citation이 운영 검토에 충분합니다.",
        tags=["grounded", "operations"],
    )
    primary_diagnostics = container.run_agent.get_diagnostics(
        tenant_id=tenant_id,
        run_id=primary_run.id,
    )
    evidence_bundle = container.run_agent.get_evidence_bundle(
        tenant_id=tenant_id,
        run_id=primary_run.id,
    )
    replay = container.run_agent.replay_run(
        tenant_id=tenant_id,
        run_id=primary_run.id,
        user_id=actor_id,
        actor_scopes=["records:read", "workflow:request"],
    )

    action_run = container.run_agent.execute(
        tenant_id=tenant_id,
        scenario="workflow-control",
        message="정책 문서를 근거로 workflow 생성 실행을 처리해줘",
        user_id=actor_id,
        actor_scopes=["records:read", "workflow:request"],
    )

    pending_approvals = container.approval.list_pending(tenant_id=tenant_id)
    summary = container.operations_summary.execute(tenant_id=tenant_id)
    usage = container.operations_usage.execute(tenant_id=tenant_id)
    slo = container.operations_slo.execute(tenant_id=tenant_id)
    alerts = container.operations_alerts.execute(tenant_id=tenant_id)
    incident = container.operations_incident_snapshot.execute(tenant_id=tenant_id)
    feedback_summary = container.agent_feedback.summary(tenant_id=tenant_id)

    output = {
        "tenant_id": tenant_id,
        "ingested_documents": ingested_documents,
        "primary_run": _run_summary(primary_run),
        "primary_diagnostics": _diagnostics_summary(primary_diagnostics),
        "primary_evidence": _evidence_summary(evidence_bundle),
        "replay": _replay_summary(replay),
        "action_run": _run_summary(action_run),
        "pending_approvals": [_approval_summary(approval) for approval in pending_approvals],
        "operations": {
            "summary": _operations_summary(summary),
            "usage": _operations_usage(usage),
            "slo": _operations_slo(slo),
            "alerts": [_alert_summary(alert) for alert in alerts],
            "incident": _incident_summary(incident),
            "feedback": _feedback_summary(feedback_summary),
        },
        "http_entrypoints": {
            "dashboard": "GET /dashboard",
            "run_export": "GET /v1/agents/runs/export",
            "audit_export": "GET /v1/audit/export",
            "approval_queue": "GET /v1/approvals/pending",
            "incident_snapshot": "GET /v1/operations/incidents/snapshot",
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default))


def _ingest_sample_docs(
    *,
    container: Any,
    tenant_id: str,
    sample_dir: Path,
    actor_id: str,
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
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
            metadata={"domain": "enterprise-ax", "language": "ko", "seed": "demo-flow"},
        )
        saved, chunk_count = container.ingest_document.execute(
            document=document,
            actor_id=actor_id,
        )
        documents.append(
            {
                "id": str(saved.id),
                "title": saved.title,
                "source_uri": saved.source_uri,
                "chunk_count": chunk_count,
            }
        )
    return documents


def _run_summary(run: Any) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "scenario": run.scenario,
        "status": run.status.value,
        "query_type": run.query_type.value,
        "confidence": run.confidence,
        "citation_count": len(run.citations),
        "trace_steps": [step.step for step in run.trace],
        "tool_decisions": [
            {
                "tool_name": execution.tool_name,
                "decision": execution.decision.value,
                "status": execution.status,
                "reason": execution.reason,
            }
            for execution in run.tool_executions
        ],
        "policy": {
            "decision": run.policy_decision.decision,
            "reason": run.policy_decision.reason,
        },
    }


def _diagnostics_summary(diagnostics: Any) -> dict[str, Any]:
    if diagnostics is None:
        return {}
    return {
        "severity": diagnostics.severity,
        "quality_score": diagnostics.quality_score,
        "metrics": diagnostics.metrics,
        "signals": [
            {
                "code": signal.code,
                "severity": signal.severity,
                "message": signal.message,
            }
            for signal in diagnostics.signals
        ],
        "recommended_actions": diagnostics.recommended_actions,
    }


def _evidence_summary(bundle: Any) -> dict[str, Any]:
    if bundle is None:
        return {}
    return {
        "evidence_hash": bundle.evidence_hash,
        "timeline_count": len(bundle.timeline),
        "audit_event_count": len(bundle.audit_events),
        "feedback_event_count": len(bundle.feedback_events),
    }


def _replay_summary(replay: Any) -> dict[str, Any]:
    if replay is None:
        return {}
    return {
        "source_run_id": str(replay.source_run.id),
        "replayed_run_id": str(replay.replayed_run.id),
        "source_status": replay.source_run.status.value,
        "replayed_status": replay.replayed_run.status.value,
        "diff": {
            "status_changed": replay.diff.status_changed,
            "query_type_changed": replay.diff.query_type_changed,
            "confidence_delta": replay.diff.confidence_delta,
            "citation_overlap_ratio": replay.diff.citation_overlap_ratio,
            "quality_score_delta": replay.diff.quality_score_delta,
            "signals_added": replay.diff.signals_added,
            "signals_resolved": replay.diff.signals_resolved,
        },
    }


def _approval_summary(approval: Any) -> dict[str, Any]:
    return {
        "id": str(approval.id),
        "agent_run_id": str(approval.agent_run_id),
        "tool_name": approval.tool_name,
        "action_type": approval.action_type.value,
        "status": approval.status.value,
        "reason": approval.reason,
        "requested_by": approval.requested_by,
    }


def _operations_summary(summary: Any) -> dict[str, Any]:
    return {
        "document_count": summary.document_count,
        "pending_approval_count": summary.pending_approval_count,
        "agent_run_count": summary.agent_run_count,
        "average_latency_ms": summary.average_latency_ms,
        "average_confidence": summary.average_confidence,
        "tool_decision_counts": summary.tool_decision_counts,
        "approval_counts": summary.approval_counts,
        "gateway_fallback_count": summary.gateway_fallback_count,
        "gateway_circuit_open_count": summary.gateway_circuit_open_count,
    }


def _operations_usage(usage: Any) -> dict[str, Any]:
    return {
        "monthly_agent_run_quota": usage.monthly_agent_run_quota,
        "agent_runs_used": usage.agent_runs_used,
        "agent_runs_remaining": usage.agent_runs_remaining,
        "usage_ratio": usage.usage_ratio,
        "exceeded": usage.exceeded,
    }


def _operations_slo(slo: Any) -> dict[str, Any]:
    return {
        "status": slo.status,
        "run_count": slo.run_count,
        "success_rate": slo.success_rate,
        "blocked_rate": slo.blocked_rate,
        "p95_latency_ms": slo.p95_latency_ms,
        "average_confidence": slo.average_confidence,
    }


def _alert_summary(alert: Any) -> dict[str, Any]:
    return {
        "code": alert.code,
        "severity": alert.severity,
        "metric": alert.metric,
        "actual_value": alert.actual_value,
        "threshold": alert.threshold,
        "message": alert.message,
    }


def _incident_summary(incident: Any) -> dict[str, Any]:
    return {
        "severity": incident.severity,
        "status": incident.status,
        "summary": incident.summary,
        "active_alert_count": incident.active_alert_count,
        "signals": incident.signals,
        "suspected_causes": incident.suspected_causes,
        "recommended_actions": incident.recommended_actions,
    }


def _feedback_summary(summary: Any) -> dict[str, Any]:
    return {
        "feedback_count": summary.feedback_count,
        "average_rating": summary.average_rating,
        "positive_count": summary.positive_count,
        "negative_count": summary.negative_count,
        "outcome_counts": summary.outcome_counts,
    }


def _json_default(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


if __name__ == "__main__":
    main()
