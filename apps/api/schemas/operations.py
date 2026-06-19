from datetime import datetime
from typing import Any

from pydantic import BaseModel


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
