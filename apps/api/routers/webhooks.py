from dataclasses import replace
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from apps.api.core.container import AppContainer, get_container
from apps.api.core.security import AuthPrincipal, require_scopes, require_tenant_access
from apps.api.domain.models import (
    WebhookDelivery,
    WebhookDeliveryStatus,
    WebhookSubscription,
)
from apps.api.schemas.webhooks import (
    CreateWebhookSubscriptionRequest,
    MarkWebhookDeliveryRequest,
    WebhookDeliveryResponse,
    WebhookSubscriptionResponse,
)

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])
ContainerDep = Annotated[AppContainer, Depends(get_container)]
WebhookReadAuth = Annotated[AuthPrincipal, Depends(require_scopes("webhooks:read"))]
WebhookWriteAuth = Annotated[AuthPrincipal, Depends(require_scopes("webhooks:write"))]


@router.post("/subscriptions", response_model=WebhookSubscriptionResponse)
def create_subscription(
    request: CreateWebhookSubscriptionRequest,
    container: ContainerDep,
    auth: WebhookWriteAuth,
) -> WebhookSubscriptionResponse:
    require_tenant_access(auth, request.tenant_id)
    subscription = WebhookSubscription(
        tenant_id=request.tenant_id,
        name=request.name,
        target_url=request.target_url,
        event_types=_normalize_event_types(request.event_types),
        secret=request.secret,
        enabled=request.enabled,
    )
    return _subscription_to_response(container.webhook_subscriptions.save(subscription))


@router.get("/subscriptions", response_model=list[WebhookSubscriptionResponse])
def list_subscriptions(
    container: ContainerDep,
    auth: WebhookReadAuth,
    tenant_id: str = "default",
) -> list[WebhookSubscriptionResponse]:
    require_tenant_access(auth, tenant_id)
    return [
        _subscription_to_response(subscription)
        for subscription in container.webhook_subscriptions.list_subscriptions(tenant_id)
    ]


@router.get("/deliveries", response_model=list[WebhookDeliveryResponse])
def list_deliveries(
    container: ContainerDep,
    auth: WebhookReadAuth,
    tenant_id: str = "default",
    status: str | None = None,
    limit: int = 100,
) -> list[WebhookDeliveryResponse]:
    require_tenant_access(auth, tenant_id)
    parsed_status = _parse_status(status)
    return [
        _delivery_to_response(delivery)
        for delivery in container.webhook_deliveries.list_deliveries(
            tenant_id=tenant_id,
            status=parsed_status,
            limit=limit,
        )
    ]


@router.post("/deliveries/{delivery_id}/mark-delivered", response_model=WebhookDeliveryResponse)
def mark_delivery_delivered(
    delivery_id: UUID,
    request: MarkWebhookDeliveryRequest,
    container: ContainerDep,
    auth: WebhookWriteAuth,
) -> WebhookDeliveryResponse:
    require_tenant_access(auth, request.tenant_id)
    delivery = _get_delivery(container, request.tenant_id, delivery_id)
    saved = container.webhook_deliveries.save(
        replace(
            delivery,
            status=WebhookDeliveryStatus.DELIVERED,
            attempt_count=delivery.attempt_count + 1,
            last_error=None,
            delivered_at=datetime.now(UTC),
        )
    )
    return _delivery_to_response(saved)


@router.post("/deliveries/{delivery_id}/mark-failed", response_model=WebhookDeliveryResponse)
def mark_delivery_failed(
    delivery_id: UUID,
    request: MarkWebhookDeliveryRequest,
    container: ContainerDep,
    auth: WebhookWriteAuth,
) -> WebhookDeliveryResponse:
    require_tenant_access(auth, request.tenant_id)
    delivery = _get_delivery(container, request.tenant_id, delivery_id)
    saved = container.webhook_deliveries.save(
        replace(
            delivery,
            status=WebhookDeliveryStatus.FAILED,
            attempt_count=delivery.attempt_count + 1,
            last_error=request.error or "delivery failed",
        )
    )
    return _delivery_to_response(saved)


def _get_delivery(container: AppContainer, tenant_id: str, delivery_id: UUID) -> WebhookDelivery:
    delivery = container.webhook_deliveries.get(tenant_id=tenant_id, delivery_id=str(delivery_id))
    if delivery is None:
        raise HTTPException(status_code=404, detail="Webhook delivery를 찾을 수 없습니다.")
    return delivery


def _normalize_event_types(event_types: list[str]) -> list[str]:
    normalized = sorted({event_type.strip() for event_type in event_types if event_type.strip()})
    return normalized or ["*"]


def _parse_status(status: str | None) -> WebhookDeliveryStatus | None:
    if status is None:
        return None
    try:
        return WebhookDeliveryStatus(status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="지원하지 않는 delivery status입니다.") from exc


def _subscription_to_response(subscription: WebhookSubscription) -> WebhookSubscriptionResponse:
    return WebhookSubscriptionResponse(
        id=subscription.id,
        tenant_id=subscription.tenant_id,
        name=subscription.name,
        target_url=subscription.target_url,
        event_types=subscription.event_types,
        enabled=subscription.enabled,
        created_at=subscription.created_at,
    )


def _delivery_to_response(delivery: WebhookDelivery) -> WebhookDeliveryResponse:
    return WebhookDeliveryResponse(
        id=delivery.id,
        tenant_id=delivery.tenant_id,
        subscription_id=delivery.subscription_id,
        event_id=delivery.event_id,
        event_type=delivery.event_type,
        target_url=delivery.target_url,
        payload=delivery.payload,
        status=delivery.status.value,
        attempt_count=delivery.attempt_count,
        next_attempt_at=delivery.next_attempt_at,
        last_error=delivery.last_error,
        created_at=delivery.created_at,
        delivered_at=delivery.delivered_at,
    )
