from __future__ import annotations

from apps.api.domain.models import QueryType, RetrievalResult, ToolExecution


class GroundedAnswerSynthesizer:
    """Deterministic local answer generator for repeatable product runs."""

    def synthesize(
        self,
        *,
        message: str,
        query_type: QueryType,
        results: list[RetrievalResult],
        tool_executions: list[ToolExecution] | None = None,
    ) -> str:
        if not results:
            return (
                "검색된 근거 문서가 부족합니다. 운영 환경에서는 답변을 보류하고 문서 적재 또는 "
                "담당자 확인 워크플로우로 넘기는 것이 안전합니다."
            )

        evidence = [self._compact(result.chunk.content) for result in results[:3]]
        prefix = self._prefix(query_type)
        bullets = "\n".join(f"- 근거 {idx + 1}: {line}" for idx, line in enumerate(evidence))
        tool_summary = self._tool_summary(tool_executions or [])
        next_actions = self._next_actions(query_type)
        return (
            f"{prefix}\n\n"
            f"요청: {message}\n\n"
            f"핵심 근거:\n{bullets}\n\n"
            f"도구 실행 상태:\n{tool_summary}\n\n"
            f"권장 실행:\n{next_actions}\n\n"
            "이 답변은 검색된 내부 문서 근거를 기준으로 생성되었으며, 쓰기 작업은 정책 검사를 "
            "통과한 경우에만 실행해야 합니다."
        )

    def _prefix(self, query_type: QueryType) -> str:
        return {
            QueryType.FACTUAL: "문서 기반으로 확인한 답변입니다.",
            QueryType.SUMMARY: "AX 전환 관점에서 요약한 결과입니다.",
            QueryType.COMPARE: "검색된 근거를 비교 관점으로 정리했습니다.",
            QueryType.ACTION: "업무 실행 전 검토해야 할 Agent 실행안입니다.",
            QueryType.RISK: "리스크와 거버넌스 관점에서 정리한 결과입니다.",
        }[query_type]

    def _next_actions(self, query_type: QueryType) -> str:
        if query_type == QueryType.ACTION:
            return "- 실행 권한 확인\n- 승인 필요 여부 판단\n- 감사로그 기록 후 tool call 처리"
        if query_type == QueryType.RISK:
            return (
                "- 개인정보/권한 경계 확인\n"
                "- 실패 시 fallback 정의\n"
                "- 감사 가능한 정책 이벤트 기록"
            )
        if query_type == QueryType.COMPARE:
            return "- 비교 기준 고정\n- 누락 문서 확인\n- 의사결정자에게 trade-off 표로 공유"
        return "- 근거 문서 확인\n- 최신성 검토\n- 필요 시 담당 시스템 API로 재확인"

    def _tool_summary(self, tool_executions: list[ToolExecution]) -> str:
        if not tool_executions:
            return "- tool 실행 없음"
        return "\n".join(
            "- "
            f"{execution.tool_name}: {execution.decision.value} "
            f"({execution.status}) - {execution.reason}"
            for execution in tool_executions
        )

    def _compact(self, text: str) -> str:
        compacted = " ".join(text.split())
        max_chars = 420
        return compacted[:max_chars] + ("..." if len(compacted) > max_chars else "")
