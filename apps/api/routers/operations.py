from typing import Annotated

from fastapi import APIRouter, Depends

from apps.api.core.container import AppContainer, get_container
from apps.api.core.security import AuthPrincipal, require_scopes, require_tenant_access
from apps.api.domain.models import OperationsSummary
from apps.api.schemas.operations import OperationsSummaryResponse

router = APIRouter(prefix="/v1/operations", tags=["operations"])
ContainerDep = Annotated[AppContainer, Depends(get_container)]
OperationsReadAuth = Annotated[AuthPrincipal, Depends(require_scopes("operations:read"))]


@router.get("/summary", response_model=OperationsSummaryResponse)
def get_operations_summary(
    container: ContainerDep,
    auth: OperationsReadAuth,
    tenant_id: str = "default",
    event_limit: int = 500,
) -> OperationsSummaryResponse:
    require_tenant_access(auth, tenant_id)
    summary = container.operations_summary.execute(
        tenant_id=tenant_id,
        event_limit=event_limit,
    )
    return _to_response(summary)


def _to_response(summary: OperationsSummary) -> OperationsSummaryResponse:
    return OperationsSummaryResponse(
        tenant_id=summary.tenant_id,
        event_limit=summary.event_limit,
        document_count=summary.document_count,
        pending_approval_count=summary.pending_approval_count,
        agent_run_count=summary.agent_run_count,
        average_latency_ms=summary.average_latency_ms,
        average_confidence=summary.average_confidence,
        event_counts=summary.event_counts,
        tool_decision_counts=summary.tool_decision_counts,
        approval_counts=summary.approval_counts,
        gateway_fallback_count=summary.gateway_fallback_count,
        latest_evaluation_metrics=summary.latest_evaluation_metrics,
        generated_at=summary.generated_at,
    )
