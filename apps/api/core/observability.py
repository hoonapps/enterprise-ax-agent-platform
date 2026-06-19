from __future__ import annotations

import logging
import time
from contextvars import ContextVar
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("apps.api.http")
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def current_request_id() -> str | None:
    return _request_id.get()


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        token = _request_id.set(request_id)
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = _elapsed_ms(started_at)
            logger.exception(
                "http.request.failed",
                extra=_log_extra(request=request, request_id=request_id, elapsed_ms=elapsed_ms),
            )
            raise
        else:
            elapsed_ms = _elapsed_ms(started_at)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.3f}"
            logger.info(
                "http.request.completed",
                extra=_log_extra(
                    request=request,
                    request_id=request_id,
                    elapsed_ms=elapsed_ms,
                    status_code=response.status_code,
                ),
            )
            return response
        finally:
            _request_id.reset(token)


def _elapsed_ms(started_at: float) -> float:
    return (time.perf_counter() - started_at) * 1000


def _log_extra(
    *,
    request: Request,
    request_id: str,
    elapsed_ms: float,
    status_code: int | None = None,
) -> dict[str, object]:
    return {
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": status_code,
        "elapsed_ms": round(elapsed_ms, 3),
        "client_host": request.client.host if request.client else None,
    }
