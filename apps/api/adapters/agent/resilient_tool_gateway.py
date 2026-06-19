from __future__ import annotations

from collections.abc import Callable
from time import perf_counter

from apps.api.application.ports import ToolGatewayPort
from apps.api.domain.models import (
    ApprovalRequest,
    ToolDefinition,
    ToolGatewayResult,
    ToolRequest,
)


class ResilientToolGateway:
    """ToolGatewayPort에 timeout, retry, fallback 정책을 적용한다."""

    def __init__(
        self,
        *,
        inner: ToolGatewayPort,
        max_attempts: int = 2,
        timeout_ms: int = 1_000,
        fallback_enabled: bool = True,
    ) -> None:
        self.inner = inner
        self.max_attempts = max(1, max_attempts)
        self.timeout_ms = max(1, timeout_ms)
        self.fallback_enabled = fallback_enabled

    def invoke(self, request: ToolRequest, definition: ToolDefinition) -> ToolGatewayResult:
        return self._execute(
            operation=lambda: self.inner.invoke(request=request, definition=definition),
            fallback_source=request.name,
        )

    def replay(self, approval: ApprovalRequest) -> ToolGatewayResult:
        return self._execute(
            operation=lambda: self.inner.replay(approval),
            fallback_source=approval.tool_name,
        )

    def _execute(
        self,
        *,
        operation: Callable[[], ToolGatewayResult],
        fallback_source: str,
    ) -> ToolGatewayResult:
        started = perf_counter()
        last_error: str | None = None

        for attempt in range(1, self.max_attempts + 1):
            attempt_started = perf_counter()
            try:
                result = operation()
                attempt_elapsed_ms = int((perf_counter() - attempt_started) * 1000)
                total_elapsed_ms = int((perf_counter() - started) * 1000)
                if attempt_elapsed_ms > self.timeout_ms:
                    last_error = (
                        f"tool gateway timeout: {attempt_elapsed_ms}ms > {self.timeout_ms}ms"
                    )
                    continue
                return self._with_operational_metadata(
                    result,
                    attempts=attempt,
                    elapsed_ms=total_elapsed_ms,
                    fallback_used=False,
                    error_message=None,
                )
            except Exception as exc:  # noqa: BLE001 - gateway boundary must absorb adapter errors
                last_error = f"{exc.__class__.__name__}: {exc}"

        total_elapsed_ms = int((perf_counter() - started) * 1000)
        if not self.fallback_enabled:
            return ToolGatewayResult(
                status="failed",
                reason="tool gateway 실행에 실패했습니다.",
                output_payload={"source": fallback_source},
                attempts=self.max_attempts,
                elapsed_ms=total_elapsed_ms,
                fallback_used=False,
                error_message=last_error,
            )

        return ToolGatewayResult(
            status="degraded",
            reason="tool gateway fallback 결과를 반환했습니다.",
            output_payload={
                "result": "fallback_result",
                "source": fallback_source,
            },
            attempts=self.max_attempts,
            elapsed_ms=total_elapsed_ms,
            fallback_used=True,
            error_message=last_error,
        )

    def _with_operational_metadata(
        self,
        result: ToolGatewayResult,
        *,
        attempts: int,
        elapsed_ms: int,
        fallback_used: bool,
        error_message: str | None,
    ) -> ToolGatewayResult:
        return ToolGatewayResult(
            status=result.status,
            output_payload=result.output_payload,
            reason=result.reason,
            attempts=attempts,
            elapsed_ms=elapsed_ms,
            fallback_used=fallback_used,
            error_message=error_message,
        )
