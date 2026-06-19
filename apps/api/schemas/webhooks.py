from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CreateWebhookSubscriptionRequest(BaseModel):
    tenant_id: str = "default"
    name: str = Field(..., min_length=1, max_length=120)
    target_url: str = Field(..., min_length=8, max_length=500)
    event_types: list[str] = Field(default_factory=lambda: ["*"])
    secret: str | None = None
    enabled: bool = True


class WebhookSubscriptionResponse(BaseModel):
    id: UUID
    tenant_id: str
    name: str
    target_url: str
    event_types: list[str]
    enabled: bool
    created_at: datetime


class WebhookDeliveryResponse(BaseModel):
    id: UUID
    tenant_id: str
    subscription_id: UUID
    event_id: UUID
    event_type: str
    target_url: str
    payload: dict[str, Any]
    status: str
    attempt_count: int
    next_attempt_at: datetime | None
    last_error: str | None
    created_at: datetime
    delivered_at: datetime | None


class MarkWebhookDeliveryRequest(BaseModel):
    tenant_id: str = "default"
    error: str | None = None
