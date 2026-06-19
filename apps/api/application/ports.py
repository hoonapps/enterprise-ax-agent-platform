from __future__ import annotations

from datetime import datetime
from typing import Protocol

from apps.api.domain.models import (
    AgentRun,
    ApprovalRequest,
    AuditEvent,
    Document,
    DocumentChunk,
    EvaluationCase,
    EvaluationRun,
    IdempotencyRecord,
    OntologyEdge,
    OntologyGraph,
    OntologyNode,
    RetrievalResult,
    ToolDefinition,
    ToolExecution,
    ToolGatewayResult,
    ToolRequest,
    WebhookDelivery,
    WebhookDeliveryStatus,
    WebhookHttpResult,
    WebhookSubscription,
)


class DocumentRepositoryPort(Protocol):
    def save_document(self, document: Document, chunks: list[DocumentChunk]) -> Document: ...

    def list_documents(self, tenant_id: str) -> list[Document]: ...


class OntologyRepositoryPort(Protocol):
    def upsert(self, nodes: list[OntologyNode], edges: list[OntologyEdge]) -> None: ...

    def get_graph(self, tenant_id: str, limit: int = 200) -> OntologyGraph: ...


class VectorSearchPort(Protocol):
    def upsert(self, chunks: list[DocumentChunk]) -> None: ...

    def search(self, tenant_id: str, query: str, top_k: int) -> list[RetrievalResult]: ...


class AuditLogPort(Protocol):
    def append(self, event: AuditEvent) -> None: ...

    def list_events(
        self,
        tenant_id: str,
        limit: int,
        event_type: str | None = None,
        resource_type: str | None = None,
        request_id: str | None = None,
    ) -> list[AuditEvent]: ...

    def count_events_before(self, tenant_id: str, before: datetime) -> int: ...

    def delete_events_before(self, tenant_id: str, before: datetime) -> int: ...


class AgentRunRepositoryPort(Protocol):
    def save(self, run: AgentRun) -> AgentRun: ...

    def get(self, tenant_id: str, run_id: str) -> AgentRun | None: ...

    def list_runs(
        self,
        tenant_id: str,
        limit: int = 50,
        scenario: str | None = None,
        status: str | None = None,
        query_type: str | None = None,
    ) -> list[AgentRun]: ...

    def count_runs_between(self, tenant_id: str, start: datetime, end: datetime) -> int: ...


class ToolRuntimePort(Protocol):
    def execute(self, request: ToolRequest) -> ToolExecution: ...

    def replay_approved(self, approval: ApprovalRequest) -> ToolExecution: ...


class ToolGatewayPort(Protocol):
    def invoke(self, request: ToolRequest, definition: ToolDefinition) -> ToolGatewayResult: ...

    def replay(self, approval: ApprovalRequest) -> ToolGatewayResult: ...


class ToolRegistryPort(Protocol):
    def list_tools(self) -> list[ToolDefinition]: ...

    def get(self, name: str) -> ToolDefinition | None: ...


class ApprovalRepositoryPort(Protocol):
    def save(self, approval: ApprovalRequest) -> ApprovalRequest: ...

    def list_pending(self, tenant_id: str) -> list[ApprovalRequest]: ...

    def get(self, tenant_id: str, approval_id: str) -> ApprovalRequest | None: ...


class EvaluationRepositoryPort(Protocol):
    def save(self, run: EvaluationRun, cases: list[EvaluationCase]) -> EvaluationRun: ...

    def get(self, tenant_id: str, evaluation_run_id: str) -> EvaluationRun | None: ...


class IdempotencyRepositoryPort(Protocol):
    def get(self, tenant_id: str, key: str) -> IdempotencyRecord | None: ...

    def save(self, record: IdempotencyRecord) -> IdempotencyRecord: ...


class WebhookSubscriptionRepositoryPort(Protocol):
    def save(self, subscription: WebhookSubscription) -> WebhookSubscription: ...

    def get(self, tenant_id: str, subscription_id: str) -> WebhookSubscription | None: ...

    def list_subscriptions(self, tenant_id: str) -> list[WebhookSubscription]: ...

    def list_enabled_for_event(
        self,
        tenant_id: str,
        event_type: str,
    ) -> list[WebhookSubscription]: ...


class WebhookDeliveryRepositoryPort(Protocol):
    def save(self, delivery: WebhookDelivery) -> WebhookDelivery: ...

    def list_deliveries(
        self,
        tenant_id: str,
        status: WebhookDeliveryStatus | None = None,
        limit: int = 100,
    ) -> list[WebhookDelivery]: ...

    def list_dispatchable(
        self,
        tenant_id: str,
        now: datetime,
        limit: int = 100,
    ) -> list[WebhookDelivery]: ...

    def claim_dispatchable(
        self,
        tenant_id: str,
        now: datetime,
        lease_until: datetime,
        limit: int = 100,
    ) -> list[WebhookDelivery]: ...

    def get(self, tenant_id: str, delivery_id: str) -> WebhookDelivery | None: ...

    def count_terminal_before(self, tenant_id: str, before: datetime) -> int: ...

    def delete_terminal_before(self, tenant_id: str, before: datetime) -> int: ...


class WebhookHttpClientPort(Protocol):
    def post_json(
        self,
        *,
        url: str,
        payload: dict[str, object],
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> WebhookHttpResult: ...
