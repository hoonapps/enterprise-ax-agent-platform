from __future__ import annotations

from typing import Protocol

from apps.api.domain.models import (
    AgentRun,
    ApprovalRequest,
    AuditEvent,
    Document,
    DocumentChunk,
    RetrievalResult,
    ToolDefinition,
    ToolExecution,
    ToolRequest,
)


class DocumentRepositoryPort(Protocol):
    def save_document(self, document: Document, chunks: list[DocumentChunk]) -> Document: ...

    def list_documents(self, tenant_id: str) -> list[Document]: ...


class VectorSearchPort(Protocol):
    def upsert(self, chunks: list[DocumentChunk]) -> None: ...

    def search(self, tenant_id: str, query: str, top_k: int) -> list[RetrievalResult]: ...


class AuditLogPort(Protocol):
    def append(self, event: AuditEvent) -> None: ...

    def list_events(self, tenant_id: str, limit: int) -> list[AuditEvent]: ...


class AgentRunRepositoryPort(Protocol):
    def save(self, run: AgentRun) -> AgentRun: ...

    def get(self, tenant_id: str, run_id: str) -> AgentRun | None: ...


class ToolRuntimePort(Protocol):
    def execute(self, request: ToolRequest) -> ToolExecution: ...

    def replay_approved(self, approval: ApprovalRequest) -> ToolExecution: ...


class ToolRegistryPort(Protocol):
    def list_tools(self) -> list[ToolDefinition]: ...

    def get(self, name: str) -> ToolDefinition | None: ...


class ApprovalRepositoryPort(Protocol):
    def save(self, approval: ApprovalRequest) -> ApprovalRequest: ...

    def list_pending(self, tenant_id: str) -> list[ApprovalRequest]: ...

    def get(self, tenant_id: str, approval_id: str) -> ApprovalRequest | None: ...
