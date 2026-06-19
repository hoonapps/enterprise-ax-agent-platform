from __future__ import annotations

import re

from apps.api.domain.models import PolicyDecision, QueryType

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
                reason="Destructive or irreversible workflow actions require human approval.",
                redactions=redactions,
            )

        return PolicyDecision(
            allowed=True,
            decision="allowed",
            reason="Request is allowed under local portfolio policy.",
            redactions=redactions,
        )
