from __future__ import annotations

from apps.api.application.ports import (
    AuditLogPort,
    WebhookDeliveryRepositoryPort,
    WebhookSubscriptionRepositoryPort,
)
from apps.api.domain.models import AuditEvent, WebhookDelivery


class OutboxAuditLog:
    def __init__(
        self,
        *,
        inner: AuditLogPort,
        subscriptions: WebhookSubscriptionRepositoryPort,
        deliveries: WebhookDeliveryRepositoryPort,
    ) -> None:
        self.inner = inner
        self.subscriptions = subscriptions
        self.deliveries = deliveries

    def append(self, event: AuditEvent) -> None:
        self.inner.append(event)
        for subscription in self.subscriptions.list_enabled_for_event(
            tenant_id=event.tenant_id,
            event_type=event.event_type,
        ):
            self.deliveries.save(
                WebhookDelivery(
                    tenant_id=event.tenant_id,
                    subscription_id=subscription.id,
                    event_id=event.id,
                    event_type=event.event_type,
                    target_url=subscription.target_url,
                    payload={
                        "id": str(event.id),
                        "tenant_id": event.tenant_id,
                        "actor_type": event.actor_type,
                        "actor_id": event.actor_id,
                        "event_type": event.event_type,
                        "resource_type": event.resource_type,
                        "resource_id": str(event.resource_id) if event.resource_id else None,
                        "payload": event.payload,
                        "created_at": event.created_at.isoformat(),
                    },
                )
            )

    def list_events(
        self,
        tenant_id: str,
        limit: int,
        event_type: str | None = None,
        resource_type: str | None = None,
    ) -> list[AuditEvent]:
        return self.inner.list_events(
            tenant_id=tenant_id,
            limit=limit,
            event_type=event_type,
            resource_type=resource_type,
        )
