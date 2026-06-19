from __future__ import annotations

from collections import defaultdict
from threading import RLock
from uuid import UUID

from apps.api.domain.models import AgentRun, AuditEvent, Document, DocumentChunk


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

    def list_events(self, tenant_id: str, limit: int) -> list[AuditEvent]:
        with self._lock:
            events = list(reversed(self._events[tenant_id]))
        return events[:limit]
