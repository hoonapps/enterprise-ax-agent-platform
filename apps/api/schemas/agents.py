from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from apps.api.schemas.common import (
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
