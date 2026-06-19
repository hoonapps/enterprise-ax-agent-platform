from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic, perf_counter

from apps.api.application.ports import ToolGatewayPort
from apps.api.domain.models import (
    ApprovalRequest,
    ToolDefinition,
    ToolGatewayCircuitStatus,
    ToolGatewayResult,
    ToolRequest,
)


@dataclass
class CircuitState:
    failure_streak: int = 0
    open_until: float = 0.0


class ResilientToolGateway:
    """ToolGatewayPort에 timeout, retry, fallback, circuit breaker 정책을 적용한다."""

    def __init__(
        self,
        *,
        inner: ToolGatewayPort,
        max_attempts: int = 2,
        timeout_ms: int = 1_000,
        fallback_enabled: bool = True,
        circuit_failure_threshold: int = 2,
        circuit_open_seconds: float = 30.0,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.inner = inner
        self.max_attempts = max(1, max_attempts)
        self.timeout_ms = max(1, timeout_ms)
        self.fallback_enabled = fallback_enabled
        self.circuit_failure_threshold = max(1, circuit_failure_threshold)
        self.circuit_open_seconds = max(0.1, circuit_open_seconds)
        self.clock = clock
        self.circuits: dict[str, CircuitState] = {}

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

    def circuit_status(
        self,
        *,
        tool_names: list[str] | None = None,
    ) -> list[ToolGatewayCircuitStatus]:
        names = sorted(set(tool_names or []) | set(self.circuits))
        return [
            self._status_for_tool(tool_name=name, circuit=self.circuits.get(name))
            for name in names
        ]

    def _execute(
        self,
        *,
        operation: Callable[[], ToolGatewayResult],
        fallback_source: str,
    ) -> ToolGatewayResult:
        started = perf_counter()
        last_error: str | None = None
        circuit = self.circuits.setdefault(fallback_source, CircuitState())
        circuit_state = self._current_circuit_state(circuit)
        if circuit_state == "open":
            return self._fallback_result(
                fallback_source=fallback_source,
                attempts=0,
                elapsed_ms=0,
                error_message="tool gateway circuit is open",
                circuit_state="open",
                circuit_open_remaining_ms=self._open_remaining_ms(circuit),
            )

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
                self._record_success(circuit)
                return self._with_operational_metadata(
                    result,
                    attempts=attempt,
                    elapsed_ms=total_elapsed_ms,
                    fallback_used=False,
                    error_message=None,
                    circuit_state="closed",
                    circuit_open_remaining_ms=0,
                )
            except Exception as exc:  # noqa: BLE001 - gateway boundary must absorb adapter errors
                last_error = f"{exc.__class__.__name__}: {exc}"

        total_elapsed_ms = int((perf_counter() - started) * 1000)
        circuit_state = self._record_failure(circuit)
        circuit_open_remaining_ms = self._open_remaining_ms(circuit)
        if not self.fallback_enabled:
            return ToolGatewayResult(
                status="failed",
                reason="tool gateway 실행에 실패했습니다.",
                output_payload={"source": fallback_source},
                attempts=self.max_attempts,
                elapsed_ms=total_elapsed_ms,
                fallback_used=False,
                error_message=last_error,
                circuit_state=circuit_state,
                circuit_open_remaining_ms=circuit_open_remaining_ms,
            )

        return self._fallback_result(
            fallback_source=fallback_source,
            attempts=self.max_attempts,
            elapsed_ms=total_elapsed_ms,
            error_message=last_error,
            circuit_state=circuit_state,
            circuit_open_remaining_ms=circuit_open_remaining_ms,
        )

    def _fallback_result(
        self,
        *,
        fallback_source: str,
        attempts: int,
        elapsed_ms: int,
        error_message: str | None,
        circuit_state: str,
        circuit_open_remaining_ms: int,
    ) -> ToolGatewayResult:
        return ToolGatewayResult(
            status="degraded",
            reason="tool gateway fallback 결과를 반환했습니다.",
            output_payload={
                "result": "fallback_result",
                "source": fallback_source,
            },
            attempts=attempts,
            elapsed_ms=elapsed_ms,
            fallback_used=True,
            error_message=error_message,
            circuit_state=circuit_state,
            circuit_open_remaining_ms=circuit_open_remaining_ms,
        )

    def _with_operational_metadata(
        self,
        result: ToolGatewayResult,
        *,
        attempts: int,
        elapsed_ms: int,
        fallback_used: bool,
        error_message: str | None,
        circuit_state: str,
        circuit_open_remaining_ms: int,
    ) -> ToolGatewayResult:
        return ToolGatewayResult(
            status=result.status,
            output_payload=result.output_payload,
            reason=result.reason,
            attempts=attempts,
            elapsed_ms=elapsed_ms,
            fallback_used=fallback_used,
            error_message=error_message,
            circuit_state=circuit_state,
            circuit_open_remaining_ms=circuit_open_remaining_ms,
        )

    def _current_circuit_state(self, circuit: CircuitState) -> str:
        if circuit.open_until <= self.clock():
            return "closed" if circuit.failure_streak == 0 else "half_open"
        return "open"

    def _record_success(self, circuit: CircuitState) -> None:
        circuit.failure_streak = 0
        circuit.open_until = 0.0

    def _record_failure(self, circuit: CircuitState) -> str:
        circuit.failure_streak += 1
        if circuit.failure_streak >= self.circuit_failure_threshold:
            circuit.open_until = self.clock() + self.circuit_open_seconds
            return "open"
        return "closed"

    def _open_remaining_ms(self, circuit: CircuitState) -> int:
        return max(0, int((circuit.open_until - self.clock()) * 1000))

    def _status_for_tool(
        self,
        *,
        tool_name: str,
        circuit: CircuitState | None,
    ) -> ToolGatewayCircuitStatus:
        if circuit is None:
            return ToolGatewayCircuitStatus(
                tool_name=tool_name,
                state="closed",
                failure_streak=0,
                open_remaining_ms=0,
                failure_threshold=self.circuit_failure_threshold,
                open_seconds=self.circuit_open_seconds,
            )
        return ToolGatewayCircuitStatus(
            tool_name=tool_name,
            state=self._current_circuit_state(circuit),
            failure_streak=circuit.failure_streak,
            open_remaining_ms=self._open_remaining_ms(circuit),
            failure_threshold=self.circuit_failure_threshold,
            open_seconds=self.circuit_open_seconds,
        )
