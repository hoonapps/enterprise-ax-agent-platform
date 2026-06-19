from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from apps.api.schemas.common import (
    AuditEventResponse,
    CitationResponse,
    PolicyResponse,
    ToolExecutionResponse,
    TraceStepResponse,
)


class RunAgentRequest(BaseModel):
    tenant_id: str = "default"
    user_id: str | None = "operator-01"
    scenario: str = Field(default="operations", examples=["operations", "finance-ops"])
    message: str = Field(..., min_length=2)
    actor_scopes: list[str] = Field(default_factory=lambda: ["records:read", "workflow:request"])
    context: dict[str, Any] = Field(default_factory=dict)


class RunAgentResponse(BaseModel):
    run_id: UUID
    tenant_id: str
    scenario: str
    status: str
    query_type: str
    answer: str
    confidence: float
    citations: list[CitationResponse]
    trace: list[TraceStepResponse]
    policy: PolicyResponse
    tool_executions: list[ToolExecutionResponse]


class AgentRunPreviewResponse(BaseModel):
    tenant_id: str
    scenario: str
    query_type: str
    redacted_query: str
    redaction_count: int
    retrieval_strategy: str
    top_k: int
    policy: PolicyResponse
    quota_allowed: bool
    quota_remaining: int
    tool_name: str | None
    tool_action_type: str | None
    tool_risk_level: str | None
    tool_description: str | None
    generated_at: datetime


class AgentRunFeedbackRequest(BaseModel):
    tenant_id: str = "default"
    rating: int = Field(..., ge=1, le=5)
    outcome: str = Field(default="accepted", min_length=2)
    submitted_by: str = Field(default="operator-01", min_length=2)
    comment: str | None = None
    tags: list[str] = Field(default_factory=list)


class AgentRunFeedbackResponse(BaseModel):
    id: UUID
    tenant_id: str
    run_id: UUID
    rating: int
    outcome: str
    submitted_by: str
    comment: str | None
    tags: list[str]
    created_at: datetime


class AgentRunSummaryResponse(BaseModel):
    run_id: UUID
    tenant_id: str
    scenario: str
    status: str
    query_type: str
    redacted_query_preview: str
    confidence: float
    citation_count: int
    tool_execution_count: int
    trace_step_count: int
    created_at: datetime
    completed_at: datetime | None


class AgentRunTimelineItemResponse(BaseModel):
    run_id: UUID
    source: str
    event_type: str
    status: str
    title: str
    detail: dict[str, Any]
    sequence: int
    occurred_at: datetime | None


class AgentRunEvidenceBundleResponse(BaseModel):
    tenant_id: str
    run_id: UUID
    run: RunAgentResponse
    timeline: list[AgentRunTimelineItemResponse]
    audit_events: list[AuditEventResponse]
    feedback_events: list[AuditEventResponse]
    evidence_hash: str = Field(..., min_length=64, max_length=64)
    generated_at: datetime


class AgentRunDiagnosticSignalResponse(BaseModel):
    code: str
    severity: str
    message: str
    detail: dict[str, Any]


class AgentRunDiagnosticsResponse(BaseModel):
    tenant_id: str
    run_id: UUID
    status: str
    severity: str
    quality_score: float
    signals: list[AgentRunDiagnosticSignalResponse]
    metrics: dict[str, Any]
    recommended_actions: list[str]
    generated_at: datetime


class AgentRunReplayRequest(BaseModel):
    tenant_id: str = "default"
    user_id: str | None = "operator-01"
    actor_scopes: list[str] = Field(default_factory=lambda: ["records:read", "workflow:request"])


class AgentRunReplayDiffResponse(BaseModel):
    source_run_id: UUID
    replayed_run_id: UUID
    status_changed: bool
    query_type_changed: bool
    confidence_delta: float
    citation_overlap_ratio: float
    source_quality_score: float
    replayed_quality_score: float
    quality_score_delta: float
    source_severity: str
    replayed_severity: str
    signals_added: list[str]
    signals_resolved: list[str]


class AgentRunReplayResponse(BaseModel):
    tenant_id: str
    source_run: RunAgentResponse
    replayed_run: RunAgentResponse
    source_diagnostics: AgentRunDiagnosticsResponse
    replayed_diagnostics: AgentRunDiagnosticsResponse
    diff: AgentRunReplayDiffResponse
    generated_at: datetime


class SearchKnowledgeRequest(BaseModel):
    tenant_id: str = "default"
    query: str = Field(..., min_length=2)
    top_k: int = Field(default=4, ge=1, le=20)


class SearchResultResponse(BaseModel):
    document_id: UUID
    chunk_id: UUID
    title: str
    source_uri: str
    score: float
    content: str


class SearchKnowledgeResponse(BaseModel):
    results: list[SearchResultResponse]
