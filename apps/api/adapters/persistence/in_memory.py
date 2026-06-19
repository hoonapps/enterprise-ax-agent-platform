from __future__ import annotations

from collections import defaultdict
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
