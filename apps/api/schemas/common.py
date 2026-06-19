from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TraceStepResponse(BaseModel):
    step: str
    status: str
    detail: dict[str, Any] = Field(default_factory=dict)


class CitationResponse(BaseModel):
    document_id: UUID
    chunk_id: UUID
    title: str
    score: float
    source_uri: str


class PolicyResponse(BaseModel):
    allowed: bool
    decision: str
    reason: str
    redactions: int


class AuditEventResponse(BaseModel):
    id: UUID
    tenant_id: str
    actor_type: str
    actor_id: str
    event_type: str
    resource_type: str
    resource_id: UUID | None
    payload: dict[str, Any]
    created_at: datetime
