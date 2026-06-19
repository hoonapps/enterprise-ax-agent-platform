from typing import Annotated

from fastapi import APIRouter, Depends

from apps.api.core.container import AppContainer, get_container
from apps.api.schemas.common import AuditEventResponse

router = APIRouter(prefix="/v1/audit", tags=["audit"])
ContainerDep = Annotated[AppContainer, Depends(get_container)]


@router.get("/events", response_model=list[AuditEventResponse])
def list_audit_events(
    container: ContainerDep,
    tenant_id: str = "default",
    limit: int = 50,
) -> list[AuditEventResponse]:
    return [
        AuditEventResponse(
            id=event.id,
            tenant_id=event.tenant_id,
            actor_type=event.actor_type,
            actor_id=event.actor_id,
            event_type=event.event_type,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            payload=event.payload,
            created_at=event.created_at,
        )
        for event in container.audit_log.list_events(tenant_id=tenant_id, limit=limit)
    ]
