from __future__ import annotations

import re

from apps.api.domain.models import (
    PolicyDecision,
    QueryType,
    ToolActionType,
    ToolDecision,
    ToolRequest,
)

EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_PATTERN = re.compile(r"\b01[016789]-?\d{3,4}-?\d{4}\b")
RESIDENT_ID_PATTERN = re.compile(r"\b\d{6}-[1-4]\d{6}\b")


class RedactionPolicy:
    def redact(self, text: str) -> tuple[str, int]:
        redacted = text
        count = 0
        for pattern, replacement in (
            (EMAIL_PATTERN, "[REDACTED_EMAIL]"),
            (PHONE_PATTERN, "[REDACTED_PHONE]"),
            (RESIDENT_ID_PATTERN, "[REDACTED_RRN]"),
        ):
            redacted, changed = pattern.subn(replacement, redacted)
            count += changed
        return redacted, count


class AgentPolicy:
    def evaluate(self, *, query_type: QueryType, message: str, redactions: int) -> PolicyDecision:
        lowered = message.lower()
        destructive_keywords = ("delete", "drop", "erase", "송금", "삭제", "결제", "퇴사처리")
        has_destructive_keyword = any(keyword in lowered for keyword in destructive_keywords)
        if query_type == QueryType.ACTION and has_destructive_keyword:
            return PolicyDecision(
                allowed=False,
                decision="approval_required",
                reason="되돌리기 어렵거나 외부 영향을 만드는 작업은 사람 승인 후 실행합니다.",
                redactions=redactions,
            )

        return PolicyDecision(
            allowed=True,
            decision="allowed",
            reason="요청이 현재 정책 기준을 통과했습니다.",
            redactions=redactions,
        )


class ToolPolicy:
    def evaluate(self, request: ToolRequest) -> tuple[ToolDecision, str]:
        if request.action_type == ToolActionType.READ:
            return ToolDecision.ALLOWED, "조회성 도구는 정책 범위 안에서 즉시 실행할 수 있습니다."

        if request.action_type == ToolActionType.APPROVAL:
            return ToolDecision.ALLOWED, "승인 요청 생성은 허용됩니다."

        if request.action_type == ToolActionType.WRITE:
            if request.risk_level in {"medium", "high"}:
                return (
                    ToolDecision.APPROVAL_REQUIRED,
                    "외부 상태를 변경하는 작업은 승인 대기 상태로 전환합니다.",
                )
            return ToolDecision.ALLOWED, "낮은 위험도의 쓰기 작업은 실행할 수 있습니다."

        return ToolDecision.DENIED, "정의되지 않은 도구 실행 유형입니다."
