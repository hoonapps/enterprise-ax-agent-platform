from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from apps.api.application.ports import AuditLogPort
from apps.api.core.observability import current_request_id
from apps.api.domain.models import AuditEvent


class RequestContextAuditLog:
    def __init__(self, inner: AuditLogPort) -> None:
        self.inner = inner

    def append(self, event: AuditEvent) -> None:
        self.inner.append(_with_request_context(event))

    def list_events(
        self,
        tenant_id: str,
        limit: int,
        event_type: str | None = None,
        resource_type: str | None = None,
        request_id: str | None = None,
    ) -> list[AuditEvent]:
        return self.inner.list_events(
            tenant_id=tenant_id,
            limit=limit,
            event_type=event_type,
            resource_type=resource_type,
            request_id=request_id,
        )

    def count_events_before(self, tenant_id: str, before: datetime) -> int:
        return self.inner.count_events_before(tenant_id, before)

    def delete_events_before(self, tenant_id: str, before: datetime) -> int:
        return self.inner.delete_events_before(tenant_id, before)


def _with_request_context(event: AuditEvent) -> AuditEvent:
    request_id = current_request_id()
    if request_id is None or "request_id" in event.payload:
        return event
    return replace(event, payload={**event.payload, "request_id": request_id})
