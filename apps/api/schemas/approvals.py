from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ApprovalResponse(BaseModel):
    id: UUID
    tenant_id: str
    agent_run_id: UUID
    tool_execution_id: UUID
    tool_name: str
    action_type: str
    input_payload: dict[str, Any]
    reason: str
    status: str
    requested_by: str | None
    approved_by: str | None
    replay_result: dict[str, Any]


class ApproveRequest(BaseModel):
    tenant_id: str = "default"
    approved_by: str = Field(..., min_length=1)


class RejectApprovalRequest(BaseModel):
    tenant_id: str = "default"
    rejected_by: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=2, max_length=500)
