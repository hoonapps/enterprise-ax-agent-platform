from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from apps.api.core.container import AppContainer, get_container
from apps.api.core.security import AuthPrincipal, require_scopes
from apps.api.domain.models import ApprovalRequest
from apps.api.schemas.approvals import ApprovalResponse, ApproveRequest, RejectApprovalRequest

router = APIRouter(prefix="/v1/approvals", tags=["approvals"])
ContainerDep = Annotated[AppContainer, Depends(get_container)]
ApprovalReadAuth = Annotated[AuthPrincipal, Depends(require_scopes("approvals:read"))]
ApprovalWriteAuth = Annotated[AuthPrincipal, Depends(require_scopes("approvals:write"))]


@router.get("/pending", response_model=list[ApprovalResponse])
def list_pending_approvals(
    container: ContainerDep,
    auth: ApprovalReadAuth,
    tenant_id: str = "default",
) -> list[ApprovalResponse]:
    return [
        _to_response(approval)
        for approval in container.approval.list_pending(tenant_id=tenant_id)
    ]


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
def approve_request(
    approval_id: UUID,
    request: ApproveRequest,
    container: ContainerDep,
    auth: ApprovalWriteAuth,
) -> ApprovalResponse:
    approval = container.approval.approve(
        tenant_id=request.tenant_id,
        approval_id=approval_id,
        approved_by=request.approved_by,
    )
    if approval is None:
        raise HTTPException(status_code=404, detail="승인 요청을 찾을 수 없습니다.")
    return _to_response(approval)


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
def reject_request(
    approval_id: UUID,
    request: RejectApprovalRequest,
    container: ContainerDep,
    auth: ApprovalWriteAuth,
) -> ApprovalResponse:
    approval = container.approval.reject(
        tenant_id=request.tenant_id,
        approval_id=approval_id,
        rejected_by=request.rejected_by,
        reason=request.reason,
    )
    if approval is None:
        raise HTTPException(status_code=404, detail="승인 요청을 찾을 수 없습니다.")
    return _to_response(approval)


def _to_response(approval: ApprovalRequest) -> ApprovalResponse:
    return ApprovalResponse(
        id=approval.id,
        tenant_id=approval.tenant_id,
        agent_run_id=approval.agent_run_id,
        tool_execution_id=approval.tool_execution_id,
        tool_name=approval.tool_name,
        action_type=approval.action_type.value,
        input_payload=approval.input_payload,
        reason=approval.reason,
        status=approval.status.value,
        requested_by=approval.requested_by,
        approved_by=approval.approved_by,
        replay_result=approval.replay_result,
    )
