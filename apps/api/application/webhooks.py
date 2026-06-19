from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from apps.api.application.ports import (
    WebhookDeliveryRepositoryPort,
    WebhookHttpClientPort,
    WebhookSubscriptionRepositoryPort,
)
from apps.api.domain.models import (
    WebhookDelivery,
    WebhookDeliveryStatus,
    WebhookHttpResult,
    WebhookSubscription,
)


class WebhookDispatcher:
    def __init__(
        self,
        *,
        subscriptions: WebhookSubscriptionRepositoryPort,
        deliveries: WebhookDeliveryRepositoryPort,
        http_client: WebhookHttpClientPort,
        timeout_seconds: float,
        max_attempts: int,
        lease_seconds: int = 60,
    ) -> None:
        self.subscriptions = subscriptions
        self.deliveries = deliveries
        self.http_client = http_client
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.lease_seconds = lease_seconds

    def dispatch(self, *, tenant_id: str, delivery_id: str) -> WebhookDelivery | None:
        delivery = self.deliveries.get(tenant_id=tenant_id, delivery_id=delivery_id)
        if delivery is None:
            return None
        if delivery.status == WebhookDeliveryStatus.DELIVERED:
            return delivery
        if delivery.attempt_count >= self.max_attempts:
            return self._mark_failed(
                delivery=delivery,
                result=WebhookHttpResult(
                    status_code=0,
                    error_message="maximum delivery attempts exceeded",
                ),
            )

        subscription = self.subscriptions.get(
            tenant_id=tenant_id,
            subscription_id=str(delivery.subscription_id),
        )
        if subscription is None or not subscription.enabled:
            return self._mark_failed(
                delivery=delivery,
                result=WebhookHttpResult(
                    status_code=0,
                    error_message="webhook subscription is not available",
                ),
            )

        result = self.http_client.post_json(
            url=delivery.target_url,
            payload=delivery.payload,
            headers=self._headers(delivery=delivery, subscription=subscription),
            timeout_seconds=self.timeout_seconds,
        )
        if result.succeeded:
            return self._mark_delivered(delivery)
        return self._mark_failed(delivery=delivery, result=result)

    def dispatch_pending(self, *, tenant_id: str, limit: int = 100) -> list[WebhookDelivery]:
        now = datetime.now(UTC)
        deliveries = self.deliveries.claim_dispatchable(
            tenant_id=tenant_id,
            now=now,
            lease_until=now + timedelta(seconds=self.lease_seconds),
            limit=limit,
        )
        dispatched: list[WebhookDelivery] = []
        for delivery in deliveries:
            result = self.dispatch(tenant_id=tenant_id, delivery_id=str(delivery.id))
            if result is not None:
                dispatched.append(result)
        return dispatched

    def _headers(
        self,
        *,
        delivery: WebhookDelivery,
        subscription: WebhookSubscription,
    ) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "X-AX-Delivery-Id": str(delivery.id),
            "X-AX-Event-Id": str(delivery.event_id),
            "X-AX-Event-Type": delivery.event_type,
        }
        if subscription.secret:
            headers["X-AX-Signature"] = self._signature(delivery.payload, subscription.secret)
        return headers

    def _signature(self, payload: dict[str, object], secret: str) -> str:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    def _mark_delivered(self, delivery: WebhookDelivery) -> WebhookDelivery:
        return self.deliveries.save(
            replace(
                delivery,
                status=WebhookDeliveryStatus.DELIVERED,
                attempt_count=delivery.attempt_count + 1,
                delivered_at=datetime.now(UTC),
                next_attempt_at=None,
                last_error=None,
            )
        )

    def _mark_failed(
        self,
        *,
        delivery: WebhookDelivery,
        result: WebhookHttpResult,
    ) -> WebhookDelivery:
        next_attempt_at = datetime.now(UTC) + timedelta(
            seconds=self._backoff_seconds(delivery.attempt_count + 1)
        )
        reason = result.error_message or f"HTTP {result.status_code}: {result.response_body}"
        return self.deliveries.save(
            replace(
                delivery,
                status=WebhookDeliveryStatus.FAILED,
                attempt_count=delivery.attempt_count + 1,
                next_attempt_at=next_attempt_at,
                last_error=reason[:500],
            )
        )

    def _backoff_seconds(self, attempt_count: int) -> int:
        backoff = 30
        for _ in range(max(0, attempt_count - 1)):
            backoff *= 2
            if backoff >= 900:
                return 900
        if backoff > 900:
            return 900
        return backoff
