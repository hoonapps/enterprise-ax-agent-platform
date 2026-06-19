from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from apps.api.schemas.common import CitationResponse, PolicyResponse, TraceStepResponse


class RunAgentRequest(BaseModel):
    tenant_id: str = "default"
    user_id: str | None = "portfolio-reviewer"
    scenario: str = Field(default="lg-cns", examples=["lg-cns", "sk-ax", "samsung-sds"])
    message: str = Field(..., min_length=2)
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
