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
