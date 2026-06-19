from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import datetime
from threading import RLock
from uuid import UUID

from apps.api.domain.models import (
    AgentRun,
    ApprovalRequest,
    ApprovalStatus,
    AuditEvent,
    Document,
    DocumentChunk,
    EvaluationCase,
    EvaluationRun,
    IdempotencyRecord,
    OntologyEdge,
    OntologyGraph,
    OntologyNode,
    WebhookDelivery,
    WebhookDeliveryStatus,
    WebhookSubscription,
)


class InMemoryDocumentRepository:
    def __init__(self) -> None:
        self._documents: dict[str, list[Document]] = defaultdict(list)
        self._chunks: dict[str, list[DocumentChunk]] = defaultdict(list)
        self._lock = RLock()

    def save_document(self, document: Document, chunks: list[DocumentChunk]) -> Document:
        with self._lock:
            self._documents[document.tenant_id].append(document)
            self._chunks[document.tenant_id].extend(chunks)
        return document

    def list_documents(self, tenant_id: str) -> list[Document]:
        with self._lock:
            return list(self._documents[tenant_id])

    def list_chunks(self, tenant_id: str) -> list[DocumentChunk]:
        with self._lock:
            return list(self._chunks[tenant_id])


class InMemoryOntologyRepository:
    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, OntologyNode]] = defaultdict(dict)
        self._edges: dict[str, dict[tuple[str, str, str], OntologyEdge]] = defaultdict(dict)
        self._lock = RLock()

    def upsert(self, nodes: list[OntologyNode], edges: list[OntologyEdge]) -> None:
        with self._lock:
            for node in nodes:
                existing_node = self._nodes[node.tenant_id].get(node.node_key)
                if existing_node is None:
                    self._nodes[node.tenant_id][node.node_key] = node
                    continue
                self._nodes[node.tenant_id][node.node_key] = OntologyNode(
                    tenant_id=existing_node.tenant_id,
                    node_key=existing_node.node_key,
                    label=existing_node.label,
                    node_type=existing_node.node_type,
                    source_document_id=existing_node.source_document_id,
                    evidence_count=existing_node.evidence_count + node.evidence_count,
                    metadata={**existing_node.metadata, **node.metadata},
                    created_at=existing_node.created_at,
                    updated_at=node.updated_at,
                )
            for edge in edges:
                edge_key = (edge.source_key, edge.target_key, edge.relation)
                existing_edge = self._edges[edge.tenant_id].get(edge_key)
                if existing_edge is None:
                    self._edges[edge.tenant_id][edge_key] = edge
                    continue
                self._edges[edge.tenant_id][edge_key] = OntologyEdge(
                    tenant_id=existing_edge.tenant_id,
                    source_key=existing_edge.source_key,
                    target_key=existing_edge.target_key,
                    relation=existing_edge.relation,
                    evidence_count=existing_edge.evidence_count + edge.evidence_count,
                    metadata={**existing_edge.metadata, **edge.metadata},
                    created_at=existing_edge.created_at,
                    updated_at=edge.updated_at,
                )

    def get_graph(self, tenant_id: str, limit: int = 200) -> OntologyGraph:
        with self._lock:
            nodes = sorted(
                self._nodes[tenant_id].values(),
                key=lambda node: (-node.evidence_count, node.node_key),
            )[:limit]
            node_keys = {node.node_key for node in nodes}
            edges = [
                edge
                for edge in sorted(
                    self._edges[tenant_id].values(),
                    key=lambda edge: (-edge.evidence_count, edge.source_key, edge.target_key),
                )
                if edge.source_key in node_keys and edge.target_key in node_keys
            ][:limit]
        return OntologyGraph(tenant_id=tenant_id, nodes=nodes, edges=edges)


class InMemoryAgentRunRepository:
    def __init__(self) -> None:
        self._runs: dict[str, dict[UUID, AgentRun]] = defaultdict(dict)
        self._lock = RLock()

    def save(self, run: AgentRun) -> AgentRun:
        with self._lock:
            self._runs[run.tenant_id][run.id] = run
        return run

    def get(self, tenant_id: str, run_id: str) -> AgentRun | None:
        with self._lock:
            try:
                return self._runs[tenant_id].get(UUID(run_id))
            except ValueError:
                return None


class InMemoryAuditLog:
    def __init__(self) -> None:
        self._events: dict[str, list[AuditEvent]] = defaultdict(list)
        self._lock = RLock()

    def append(self, event: AuditEvent) -> None:
        with self._lock:
            self._events[event.tenant_id].append(event)

    def list_events(
        self,
        tenant_id: str,
        limit: int,
        event_type: str | None = None,
        resource_type: str | None = None,
    ) -> list[AuditEvent]:
        with self._lock:
            events = list(reversed(self._events[tenant_id]))
        if event_type is not None:
            events = [event for event in events if event.event_type == event_type]
        if resource_type is not None:
            events = [event for event in events if event.resource_type == resource_type]
        return events[:limit]


class InMemoryApprovalRepository:
    def __init__(self) -> None:
        self._approvals: dict[str, dict[UUID, ApprovalRequest]] = defaultdict(dict)
        self._lock = RLock()

    def save(self, approval: ApprovalRequest) -> ApprovalRequest:
        with self._lock:
            self._approvals[approval.tenant_id][approval.id] = approval
        return approval

    def list_pending(self, tenant_id: str) -> list[ApprovalRequest]:
        with self._lock:
            approvals = list(self._approvals[tenant_id].values())
        return [approval for approval in approvals if approval.status == ApprovalStatus.PENDING]

    def get(self, tenant_id: str, approval_id: str) -> ApprovalRequest | None:
        with self._lock:
            try:
                return self._approvals[tenant_id].get(UUID(approval_id))
            except ValueError:
                return None


class InMemoryEvaluationRepository:
    def __init__(self) -> None:
        self._runs: dict[str, dict[UUID, EvaluationRun]] = defaultdict(dict)
        self._cases: dict[str, dict[UUID, list[EvaluationCase]]] = defaultdict(dict)
        self._lock = RLock()

    def save(self, run: EvaluationRun, cases: list[EvaluationCase]) -> EvaluationRun:
        saved = EvaluationRun(
            id=run.id,
            tenant_id=run.tenant_id,
            name=run.name,
            scenario=run.scenario,
            status=run.status,
            metrics=run.metrics,
            cases=cases,
            created_at=run.created_at,
            completed_at=run.completed_at,
        )
        with self._lock:
            self._runs[run.tenant_id][run.id] = saved
            self._cases[run.tenant_id][run.id] = list(cases)
        return saved

    def get(self, tenant_id: str, evaluation_run_id: str) -> EvaluationRun | None:
        with self._lock:
            try:
                run_id = UUID(evaluation_run_id)
            except ValueError:
                return None
            run = self._runs[tenant_id].get(run_id)
            if run is None:
                return None
            cases = list(self._cases[tenant_id].get(run_id, []))
        return EvaluationRun(
            id=run.id,
            tenant_id=run.tenant_id,
            name=run.name,
            scenario=run.scenario,
            status=run.status,
            metrics=run.metrics,
            cases=cases,
            created_at=run.created_at,
            completed_at=run.completed_at,
        )


class InMemoryIdempotencyRepository:
    def __init__(self) -> None:
        self._records: dict[str, dict[str, IdempotencyRecord]] = defaultdict(dict)
        self._lock = RLock()

    def get(self, tenant_id: str, key: str) -> IdempotencyRecord | None:
        with self._lock:
            return self._records[tenant_id].get(key)

    def save(self, record: IdempotencyRecord) -> IdempotencyRecord:
        with self._lock:
            self._records[record.tenant_id][record.key] = record
        return record


class InMemoryWebhookSubscriptionRepository:
    def __init__(self) -> None:
        self._subscriptions: dict[str, dict[UUID, WebhookSubscription]] = defaultdict(dict)
        self._lock = RLock()

    def save(self, subscription: WebhookSubscription) -> WebhookSubscription:
        with self._lock:
            self._subscriptions[subscription.tenant_id][subscription.id] = subscription
        return subscription

    def get(self, tenant_id: str, subscription_id: str) -> WebhookSubscription | None:
        with self._lock:
            try:
                return self._subscriptions[tenant_id].get(UUID(subscription_id))
            except ValueError:
                return None

    def list_subscriptions(self, tenant_id: str) -> list[WebhookSubscription]:
        with self._lock:
            subscriptions = list(self._subscriptions[tenant_id].values())
        return sorted(subscriptions, key=lambda item: item.created_at, reverse=True)

    def list_enabled_for_event(
        self,
        tenant_id: str,
        event_type: str,
    ) -> list[WebhookSubscription]:
        return [
            subscription
            for subscription in self.list_subscriptions(tenant_id)
            if subscription.enabled
            and ("*" in subscription.event_types or event_type in subscription.event_types)
        ]


class InMemoryWebhookDeliveryRepository:
    def __init__(self) -> None:
        self._deliveries: dict[str, dict[UUID, WebhookDelivery]] = defaultdict(dict)
        self._lock = RLock()

    def save(self, delivery: WebhookDelivery) -> WebhookDelivery:
        with self._lock:
            self._deliveries[delivery.tenant_id][delivery.id] = delivery
        return delivery

    def list_deliveries(
        self,
        tenant_id: str,
        status: WebhookDeliveryStatus | None = None,
        limit: int = 100,
    ) -> list[WebhookDelivery]:
        with self._lock:
            deliveries = list(self._deliveries[tenant_id].values())
        if status is not None:
            deliveries = [delivery for delivery in deliveries if delivery.status == status]
        return sorted(deliveries, key=lambda item: item.created_at, reverse=True)[:limit]

    def list_dispatchable(
        self,
        tenant_id: str,
        now: datetime,
        limit: int = 100,
    ) -> list[WebhookDelivery]:
        with self._lock:
            deliveries = list(self._deliveries[tenant_id].values())
        dispatchable = [
            delivery
            for delivery in deliveries
            if _is_dispatchable_delivery(delivery=delivery, now=now)
        ]
        return sorted(
            dispatchable,
            key=lambda item: item.next_attempt_at or item.created_at,
        )[:limit]

    def claim_dispatchable(
        self,
        tenant_id: str,
        now: datetime,
        lease_until: datetime,
        limit: int = 100,
    ) -> list[WebhookDelivery]:
        with self._lock:
            dispatchable = [
                delivery
                for delivery in self._deliveries[tenant_id].values()
                if _is_dispatchable_delivery(delivery=delivery, now=now)
            ]
            claimed = [
                replace(
                    delivery,
                    status=WebhookDeliveryStatus.DISPATCHING,
                    next_attempt_at=lease_until,
                )
                for delivery in sorted(
                    dispatchable,
                    key=lambda item: item.next_attempt_at or item.created_at,
                )[:limit]
            ]
            for delivery in claimed:
                self._deliveries[tenant_id][delivery.id] = delivery
        return claimed

    def get(self, tenant_id: str, delivery_id: str) -> WebhookDelivery | None:
        with self._lock:
            try:
                return self._deliveries[tenant_id].get(UUID(delivery_id))
            except ValueError:
                return None


def _is_dispatchable_delivery(*, delivery: WebhookDelivery, now: datetime) -> bool:
    if delivery.status == WebhookDeliveryStatus.PENDING:
        return True
    if delivery.status in {WebhookDeliveryStatus.FAILED, WebhookDeliveryStatus.DISPATCHING}:
        return delivery.next_attempt_at is None or delivery.next_attempt_at <= now
    return False
