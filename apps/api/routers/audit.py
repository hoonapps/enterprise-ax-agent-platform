import csv
import json
from io import StringIO
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response

from apps.api.core.container import AppContainer, get_container
from apps.api.core.security import AuthPrincipal, require_scopes, require_tenant_access
from apps.api.domain.models import AuditEvent
from apps.api.schemas.common import AuditEventResponse

router = APIRouter(prefix="/v1/audit", tags=["audit"])
ContainerDep = Annotated[AppContainer, Depends(get_container)]
AuditReadAuth = Annotated[AuthPrincipal, Depends(require_scopes("audit:read"))]


@router.get("/events", response_model=list[AuditEventResponse])
def list_audit_events(
    container: ContainerDep,
    auth: AuditReadAuth,
    tenant_id: str = "default",
    limit: int = 50,
    event_type: str | None = None,
    resource_type: str | None = None,
) -> list[AuditEventResponse]:
    require_tenant_access(auth, tenant_id)
    events = container.audit_log.list_events(
        tenant_id=tenant_id,
        limit=limit,
        event_type=event_type,
        resource_type=resource_type,
    )
    return [_to_response(event) for event in events]


@router.get("/export")
def export_audit_events(
    container: ContainerDep,
    auth: AuditReadAuth,
    tenant_id: str = "default",
    limit: int = 500,
    event_type: str | None = None,
    resource_type: str | None = None,
    format: str = "jsonl",
) -> Response:
    require_tenant_access(auth, tenant_id)
    events = container.audit_log.list_events(
        tenant_id=tenant_id,
        limit=limit,
        event_type=event_type,
        resource_type=resource_type,
    )
    if format == "jsonl":
        return Response(
            content=_to_jsonl(events),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": 'attachment; filename="audit-events.jsonl"'},
        )
    if format == "csv":
        return Response(
            content=_to_csv(events),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="audit-events.csv"'},
        )
    raise HTTPException(status_code=400, detail="지원하지 않는 export format입니다.")


def _to_response(event: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse(
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


def _to_jsonl(events: list[AuditEvent]) -> str:
    return "\n".join(json.dumps(_event_dict(event), ensure_ascii=False) for event in events) + (
        "\n" if events else ""
    )


def _to_csv(events: list[AuditEvent]) -> str:
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id",
            "tenant_id",
            "actor_type",
            "actor_id",
            "event_type",
            "resource_type",
            "resource_id",
            "payload",
            "created_at",
        ],
    )
    writer.writeheader()
    for event in events:
        row = _event_dict(event)
        row["payload"] = json.dumps(event.payload, ensure_ascii=False, sort_keys=True)
        writer.writerow(row)
    return output.getvalue()


def _event_dict(event: AuditEvent) -> dict[str, str | dict[str, object] | None]:
    return {
        "id": str(event.id),
        "tenant_id": event.tenant_id,
        "actor_type": event.actor_type,
        "actor_id": event.actor_id,
        "event_type": event.event_type,
        "resource_type": event.resource_type,
        "resource_id": _uuid_to_str(event.resource_id),
        "payload": event.payload,
        "created_at": event.created_at.isoformat(),
    }


def _uuid_to_str(value: UUID | None) -> str | None:
    return str(value) if value is not None else None
