from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OperationsSummaryResponse(BaseModel):
    tenant_id: str
    event_limit: int
    document_count: int
    pending_approval_count: int
    agent_run_count: int
    average_latency_ms: float
    average_confidence: float
    event_counts: dict[str, int]
    tool_decision_counts: dict[str, int]
    approval_counts: dict[str, int]
    gateway_fallback_count: int
    latest_evaluation_metrics: dict[str, Any]
    generated_at: datetime


class OperationsUsageResponse(BaseModel):
    tenant_id: str
    period_start: datetime
    period_end: datetime
    monthly_agent_run_quota: int
    agent_runs_used: int
    agent_runs_remaining: int
    usage_ratio: float
    exceeded: bool
    generated_at: datetime


class OperationsSloResponse(BaseModel):
    tenant_id: str
    event_limit: int
    run_count: int
    success_count: int
    blocked_count: int
    failed_count: int
    success_rate: float
    blocked_rate: float
    p95_latency_ms: float
    average_confidence: float
    latency_target_ms: int
    success_rate_target: float
    error_budget_remaining: float
    status: str
    generated_at: datetime


class OperationsIncidentSnapshotResponse(BaseModel):
    tenant_id: str
    severity: str
    status: str
    summary: str
    active_alert_count: int
    signals: list[str]
    suspected_causes: list[str]
    recommended_actions: list[str]
    generated_at: datetime


class AgentFeedbackSummaryResponse(BaseModel):
    tenant_id: str
    event_limit: int
    feedback_count: int
    average_rating: float
    positive_count: int
    negative_count: int
    outcome_counts: dict[str, int]
    generated_at: datetime


class OperationsAlertResponse(BaseModel):
    tenant_id: str
    code: str
    severity: str
    message: str
    metric: str
    actual_value: float
    threshold: float
    generated_at: datetime


class RetentionPruneRequest(BaseModel):
    tenant_id: str = "default"
    audit_older_than_days: int = Field(default=90, ge=1, le=3650)
    webhook_older_than_days: int = Field(default=30, ge=1, le=3650)
    dry_run: bool = True


class RetentionPruneResponse(BaseModel):
    tenant_id: str
    dry_run: bool
    audit_cutoff: datetime
    webhook_cutoff: datetime
    audit_events_matched: int
    webhook_deliveries_matched: int
    audit_events_deleted: int
    webhook_deliveries_deleted: int
    generated_at: datetime
