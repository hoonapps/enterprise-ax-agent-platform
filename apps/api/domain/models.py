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


class ToolActionType(StrEnum):
    READ = "read"
    WRITE = "write"
    APPROVAL = "approval"


class ToolDecision(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    APPROVAL_REQUIRED = "approval_required"
    NOT_REQUIRED = "not_required"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    EXECUTED = "executed"
    REJECTED = "rejected"


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
class ToolRequest:
    name: str
    action_type: ToolActionType
    input_payload: dict[str, Any]
    actor_scopes: list[str] = field(default_factory=list)
    risk_level: str = "low"
    description: str = ""


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    action_type: ToolActionType
    required_scope: str
    risk_level: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


@dataclass(frozen=True)
class ToolExecution:
    tool_name: str
    action_type: ToolActionType
    decision: ToolDecision
    status: str
    reason: str
    input_payload: dict[str, Any] = field(default_factory=dict)
    output_payload: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class ToolGatewayResult:
    status: str
    output_payload: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass(frozen=True)
class ApprovalRequest:
    tenant_id: str
    agent_run_id: UUID
    tool_execution_id: UUID
    tool_name: str
    action_type: ToolActionType
    input_payload: dict[str, Any]
    reason: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_by: str | None = None
    approved_by: str | None = None
    replay_result: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


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
    tool_executions: list[ToolExecution] = field(default_factory=list)
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
