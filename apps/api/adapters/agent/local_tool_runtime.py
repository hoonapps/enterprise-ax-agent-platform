from __future__ import annotations

from uuid import uuid4

from apps.api.domain.models import (
    ApprovalRequest,
    ToolActionType,
    ToolDecision,
    ToolExecution,
    ToolRequest,
)
from apps.api.domain.policies import ToolPolicy


class LocalToolRuntime:
    """외부 시스템 대신 tool 실행 경계를 검증하는 로컬 runtime."""

    def __init__(self, policy: ToolPolicy) -> None:
        self.policy = policy

    def execute(self, request: ToolRequest) -> ToolExecution:
        decision, reason = self.policy.evaluate(request)

        if decision == ToolDecision.APPROVAL_REQUIRED:
            execution_id = uuid4()
            return ToolExecution(
                id=execution_id,
                tool_name=request.name,
                action_type=request.action_type,
                decision=decision,
                status="pending_approval",
                reason=reason,
                input_payload=request.input_payload,
                output_payload={
                    "approval_ticket": f"approval://{execution_id}",
                    "description": request.description,
                },
            )

        if decision == ToolDecision.DENIED:
            return ToolExecution(
                tool_name=request.name,
                action_type=request.action_type,
                decision=decision,
                status="skipped",
                reason=reason,
                input_payload=request.input_payload,
            )

        if request.action_type == ToolActionType.READ:
            output_payload = {
                "result": "local_runtime_read_result",
                "source": request.name,
                "data": request.input_payload,
            }
        else:
            output_payload = {
                "result": "local_runtime_action_recorded",
                "source": request.name,
            }

        return ToolExecution(
            tool_name=request.name,
            action_type=request.action_type,
            decision=decision,
            status="succeeded",
            reason=reason,
            input_payload=request.input_payload,
            output_payload=output_payload,
        )

    def replay_approved(self, approval: ApprovalRequest) -> ToolExecution:
        return ToolExecution(
            tool_name=approval.tool_name,
            action_type=approval.action_type,
            decision=ToolDecision.ALLOWED,
            status="succeeded",
            reason="승인된 tool 요청을 replay했습니다.",
            input_payload=approval.input_payload,
            output_payload={
                "result": "approved_action_replayed",
                "approval_id": str(approval.id),
                "tool_execution_id": str(approval.tool_execution_id),
            },
        )
