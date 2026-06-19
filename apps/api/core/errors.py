from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from apps.api.core.observability import current_request_id

ExceptionHandler = Callable[[Request, Exception], JSONResponse | Awaitable[JSONResponse]]


def install_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        StarletteHTTPException,
        cast(ExceptionHandler, http_exception_handler),
    )
    app.add_exception_handler(
        RequestValidationError,
        cast(ExceptionHandler, validation_exception_handler),
    )
    app.add_exception_handler(Exception, unhandled_exception_handler)


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(_error_body(request=request, detail=exc.detail)),
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(_error_body(request=request, detail=exc.errors())),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=jsonable_encoder(_error_body(request=request, detail="Internal Server Error")),
    )


def _error_body(*, request: Request, detail: object) -> dict[str, object]:
    return {
        "detail": detail,
        "request_id": current_request_id() or request.headers.get("X-Request-ID"),
    }
