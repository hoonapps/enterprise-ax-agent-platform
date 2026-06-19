from typing import Annotated

from fastapi import APIRouter, Depends

from apps.api.core.container import AppContainer, get_container
from apps.api.core.security import AuthPrincipal, require_scopes, require_tenant_access
from apps.api.domain.models import (
    AgentFeedbackSummary,
    MigrationStatus,
    OperationsAlert,
    OperationsIncidentSnapshot,
    OperationsSlo,
    OperationsSummary,
    OperationsUsage,
    RetentionPruneResult,
)
from apps.api.schemas.operations import (
    AgentFeedbackSummaryResponse,
    MigrationStatusItemResponse,
    MigrationStatusResponse,
    OperationsAlertResponse,
    OperationsIncidentSnapshotResponse,
    OperationsSloResponse,
    OperationsSummaryResponse,
    OperationsUsageResponse,
    RetentionPruneRequest,
    RetentionPruneResponse,
)

router = APIRouter(prefix="/v1/operations", tags=["operations"])
ContainerDep = Annotated[AppContainer, Depends(get_container)]
OperationsReadAuth = Annotated[AuthPrincipal, Depends(require_scopes("operations:read"))]
OperationsWriteAuth = Annotated[AuthPrincipal, Depends(require_scopes("operations:write"))]


@router.get("/summary", response_model=OperationsSummaryResponse)
def get_operations_summary(
    container: ContainerDep,
    auth: OperationsReadAuth,
    tenant_id: str = "default",
    event_limit: int = 500,
) -> OperationsSummaryResponse:
    require_tenant_access(auth, tenant_id)
    summary = container.operations_summary.execute(
        tenant_id=tenant_id,
        event_limit=event_limit,
    )
    return _to_response(summary)


@router.get("/usage", response_model=OperationsUsageResponse)
def get_operations_usage(
    container: ContainerDep,
    auth: OperationsReadAuth,
    tenant_id: str = "default",
) -> OperationsUsageResponse:
    require_tenant_access(auth, tenant_id)
    usage = container.operations_usage.execute(tenant_id=tenant_id)
    return _usage_to_response(usage)


@router.get("/slo", response_model=OperationsSloResponse)
def get_operations_slo(
    container: ContainerDep,
    auth: OperationsReadAuth,
    tenant_id: str = "default",
    event_limit: int = 500,
    latency_target_ms: int = 3000,
    success_rate_target: float = 0.95,
) -> OperationsSloResponse:
    require_tenant_access(auth, tenant_id)
    slo = container.operations_slo.execute(
        tenant_id=tenant_id,
        event_limit=event_limit,
        latency_target_ms=latency_target_ms,
        success_rate_target=success_rate_target,
    )
    return _slo_to_response(slo)


@router.get("/incidents/snapshot", response_model=OperationsIncidentSnapshotResponse)
def get_operations_incident_snapshot(
    container: ContainerDep,
    auth: OperationsReadAuth,
    tenant_id: str = "default",
    event_limit: int = 500,
) -> OperationsIncidentSnapshotResponse:
    require_tenant_access(auth, tenant_id)
    snapshot = container.operations_incident_snapshot.execute(
        tenant_id=tenant_id,
        event_limit=event_limit,
    )
    return _incident_snapshot_to_response(snapshot)


@router.get("/feedback/summary", response_model=AgentFeedbackSummaryResponse)
def get_agent_feedback_summary(
    container: ContainerDep,
    auth: OperationsReadAuth,
    tenant_id: str = "default",
    event_limit: int = 500,
) -> AgentFeedbackSummaryResponse:
    require_tenant_access(auth, tenant_id)
    summary = container.agent_feedback.summary(tenant_id=tenant_id, event_limit=event_limit)
    return _feedback_summary_to_response(summary)


@router.get("/alerts", response_model=list[OperationsAlertResponse])
def get_operations_alerts(
    container: ContainerDep,
    auth: OperationsReadAuth,
    tenant_id: str = "default",
    event_limit: int = 500,
    max_pending_approvals: int = 20,
    max_average_latency_ms: int = 3000,
    min_average_confidence: float = 0.55,
    max_gateway_fallbacks: int = 0,
    min_evaluation_pass_rate: float = 0.85,
    max_monthly_usage_ratio: float = 0.9,
) -> list[OperationsAlertResponse]:
    require_tenant_access(auth, tenant_id)
    alerts = container.operations_alerts.execute(
        tenant_id=tenant_id,
        event_limit=event_limit,
        max_pending_approvals=max_pending_approvals,
        max_average_latency_ms=max_average_latency_ms,
        min_average_confidence=min_average_confidence,
        max_gateway_fallbacks=max_gateway_fallbacks,
        min_evaluation_pass_rate=min_evaluation_pass_rate,
        max_monthly_usage_ratio=max_monthly_usage_ratio,
    )
    return [_alert_to_response(alert) for alert in alerts]


@router.get("/migrations/status", response_model=MigrationStatusResponse)
def get_migration_status(
    container: ContainerDep,
    auth: OperationsReadAuth,
) -> MigrationStatusResponse:
    _ = auth
    status = container.migration_status.execute()
    return _migration_status_to_response(status)


@router.post("/retention/prune", response_model=RetentionPruneResponse)
def prune_retention(
    payload: RetentionPruneRequest,
    container: ContainerDep,
    auth: OperationsWriteAuth,
) -> RetentionPruneResponse:
    require_tenant_access(auth, payload.tenant_id)
    result = container.retention_prune.execute(
        tenant_id=payload.tenant_id,
        audit_older_than_days=payload.audit_older_than_days,
        webhook_older_than_days=payload.webhook_older_than_days,
        dry_run=payload.dry_run,
        actor_id=auth.actor_id,
    )
    return _retention_to_response(result)


def _to_response(summary: OperationsSummary) -> OperationsSummaryResponse:
    return OperationsSummaryResponse(
        tenant_id=summary.tenant_id,
        event_limit=summary.event_limit,
        document_count=summary.document_count,
        pending_approval_count=summary.pending_approval_count,
        agent_run_count=summary.agent_run_count,
        average_latency_ms=summary.average_latency_ms,
        average_confidence=summary.average_confidence,
        event_counts=summary.event_counts,
        tool_decision_counts=summary.tool_decision_counts,
        approval_counts=summary.approval_counts,
        gateway_fallback_count=summary.gateway_fallback_count,
        latest_evaluation_metrics=summary.latest_evaluation_metrics,
        generated_at=summary.generated_at,
    )


def _usage_to_response(usage: OperationsUsage) -> OperationsUsageResponse:
    return OperationsUsageResponse(
        tenant_id=usage.tenant_id,
        period_start=usage.period_start,
        period_end=usage.period_end,
        monthly_agent_run_quota=usage.monthly_agent_run_quota,
        agent_runs_used=usage.agent_runs_used,
        agent_runs_remaining=usage.agent_runs_remaining,
        usage_ratio=usage.usage_ratio,
        exceeded=usage.exceeded,
        generated_at=usage.generated_at,
    )


def _slo_to_response(slo: OperationsSlo) -> OperationsSloResponse:
    return OperationsSloResponse(
        tenant_id=slo.tenant_id,
        event_limit=slo.event_limit,
        run_count=slo.run_count,
        success_count=slo.success_count,
        blocked_count=slo.blocked_count,
        failed_count=slo.failed_count,
        success_rate=slo.success_rate,
        blocked_rate=slo.blocked_rate,
        p95_latency_ms=slo.p95_latency_ms,
        average_confidence=slo.average_confidence,
        latency_target_ms=slo.latency_target_ms,
        success_rate_target=slo.success_rate_target,
        error_budget_remaining=slo.error_budget_remaining,
        status=slo.status,
        generated_at=slo.generated_at,
    )


def _incident_snapshot_to_response(
    snapshot: OperationsIncidentSnapshot,
) -> OperationsIncidentSnapshotResponse:
    return OperationsIncidentSnapshotResponse(
        tenant_id=snapshot.tenant_id,
        severity=snapshot.severity,
        status=snapshot.status,
        summary=snapshot.summary,
        active_alert_count=snapshot.active_alert_count,
        signals=snapshot.signals,
        suspected_causes=snapshot.suspected_causes,
        recommended_actions=snapshot.recommended_actions,
        generated_at=snapshot.generated_at,
    )


def _feedback_summary_to_response(summary: AgentFeedbackSummary) -> AgentFeedbackSummaryResponse:
    return AgentFeedbackSummaryResponse(
        tenant_id=summary.tenant_id,
        event_limit=summary.event_limit,
        feedback_count=summary.feedback_count,
        average_rating=summary.average_rating,
        positive_count=summary.positive_count,
        negative_count=summary.negative_count,
        outcome_counts=summary.outcome_counts,
        generated_at=summary.generated_at,
    )


def _migration_status_to_response(status: MigrationStatus) -> MigrationStatusResponse:
    return MigrationStatusResponse(
        storage_backend=status.storage_backend,
        ledger_available=status.ledger_available,
        status=status.status,
        migrations=[
            MigrationStatusItemResponse(
                version=item.version,
                filename=item.filename,
                checksum=item.checksum,
                applied_checksum=item.applied_checksum,
                status=item.status,
                applied_at=item.applied_at,
            )
            for item in status.migrations
        ],
        generated_at=status.generated_at,
    )


def _alert_to_response(alert: OperationsAlert) -> OperationsAlertResponse:
    return OperationsAlertResponse(
        tenant_id=alert.tenant_id,
        code=alert.code,
        severity=alert.severity,
        message=alert.message,
        metric=alert.metric,
        actual_value=alert.actual_value,
        threshold=alert.threshold,
        generated_at=alert.generated_at,
    )


def _retention_to_response(result: RetentionPruneResult) -> RetentionPruneResponse:
    return RetentionPruneResponse(
        tenant_id=result.tenant_id,
        dry_run=result.dry_run,
        audit_cutoff=result.audit_cutoff,
        webhook_cutoff=result.webhook_cutoff,
        audit_events_matched=result.audit_events_matched,
        webhook_deliveries_matched=result.webhook_deliveries_matched,
        audit_events_deleted=result.audit_events_deleted,
        webhook_deliveries_deleted=result.webhook_deliveries_deleted,
        generated_at=result.generated_at,
    )
