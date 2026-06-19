from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class QueryType(StrEnum):
    FACTUAL = "factual"
    SUMMARY = "summary"
    COMPARE = "compare"
    ACTION = "action"
    RISK = "risk"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


class Classification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass(frozen=True)
class Document:
    tenant_id: str
    title: str
    content: str
    source_type: str = "manual"
    source_uri: str = "local"
    classification: Classification = Classification.INTERNAL
    metadata: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class DocumentChunk:
    tenant_id: str
    document_id: UUID
    chunk_index: int
    content: str
    title: str
    source_uri: str
    classification: Classification
    metadata: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)

    @property
    def embedding_ref(self) -> str:
        return str(self.id)


@dataclass(frozen=True)
class Citation:
    document_id: UUID
    chunk_id: UUID
    title: str
    score: float
    source_uri: str


@dataclass(frozen=True)
class RetrievalResult:
    chunk: DocumentChunk
    score: float

    def citation(self) -> Citation:
        return Citation(
            document_id=self.chunk.document_id,
            chunk_id=self.chunk.id,
            title=self.chunk.title,
            score=round(self.score, 4),
            source_uri=self.chunk.source_uri,
        )


@dataclass(frozen=True)
class TraceStep:
    step: str
    status: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    decision: str
    reason: str
    redactions: int = 0


@dataclass(frozen=True)
class AgentRun:
    tenant_id: str
    scenario: str
    query: str
    redacted_query: str
    query_type: QueryType
    answer: str
    status: RunStatus
    citations: list[Citation]
    trace: list[TraceStep]
    confidence: float
    policy_decision: PolicyDecision
    user_id: str | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


@dataclass(frozen=True)
class AuditEvent:
    tenant_id: str
    actor_type: str
    actor_id: str
    event_type: str
    resource_type: str
    payload: dict[str, Any]
    resource_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
