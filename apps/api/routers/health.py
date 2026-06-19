from __future__ import annotations

import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

import psycopg
from fastapi import APIRouter, Response, status

from apps.api.core.config import get_settings
from apps.api.schemas.health import DependencyCheckResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": get_settings().app_name}


@router.get("/v1/readiness", response_model=ReadinessResponse)
def readiness(response: Response) -> ReadinessResponse:
    settings = get_settings()
    dependencies = [
        _check_storage(settings.storage_backend, settings.postgres_dsn),
        _check_vector(
            vector_backend=settings.vector_backend,
            qdrant_url=settings.qdrant_url,
            qdrant_collection=settings.qdrant_collection,
        ),
        _check_static(
            name="llm",
            detail={"mode": settings.llm_mode},
        ),
        _check_static(
            name="auth",
            detail={"mode": settings.auth_mode},
        ),
    ]
    ready = all(item.status == "ready" for item in dependencies)
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if ready else "degraded",
        environment=settings.app_env,
        llm_mode=settings.llm_mode,
        storage_backend=settings.storage_backend,
        vector_backend=settings.vector_backend,
        auth_mode=settings.auth_mode,
        dependencies=dependencies,
    )


def _check_storage(storage_backend: str, postgres_dsn: str) -> DependencyCheckResponse:
    if storage_backend != "postgres":
        return _check_static(name="storage", detail={"backend": storage_backend})

    def probe() -> dict[str, str]:
        with psycopg.connect(postgres_dsn, connect_timeout=2) as conn:
            row = conn.execute("select current_database(), current_user").fetchone()
        database = str(row[0]) if row else "unknown"
        user = str(row[1]) if row else "unknown"
        return {"backend": "postgres", "database": database, "user": user}

    return _measure("storage", probe)


def _check_vector(
    *,
    vector_backend: str,
    qdrant_url: str,
    qdrant_collection: str,
) -> DependencyCheckResponse:
    if vector_backend != "qdrant":
        return _check_static(name="vector", detail={"backend": vector_backend})

    def probe() -> dict[str, str]:
        endpoint = f"{qdrant_url.rstrip('/')}/collections"
        request = urllib.request.Request(endpoint, method="GET")
        with urllib.request.urlopen(request, timeout=2) as result:
            return {
                "backend": "qdrant",
                "collection": qdrant_collection,
                "http_status": str(result.status),
            }

    return _measure("vector", probe)


def _check_static(*, name: str, detail: dict[str, str]) -> DependencyCheckResponse:
    return DependencyCheckResponse(name=name, status="ready", latency_ms=0, detail=detail)


def _measure(
    name: str,
    probe: Callable[[], dict[str, str]],
) -> DependencyCheckResponse:
    started = time.perf_counter()
    try:
        detail = probe()
        check_status = "ready"
    except (OSError, TimeoutError, psycopg.Error, urllib.error.URLError) as exc:
        detail = {"error": exc.__class__.__name__, "message": str(exc)}
        check_status = "unavailable"
    latency_ms = max(0, round((time.perf_counter() - started) * 1000))
    return DependencyCheckResponse(
        name=name,
        status=check_status,
        latency_ms=latency_ms,
        detail=_stringify_detail(detail),
    )


def _stringify_detail(detail: dict[str, Any]) -> dict[str, str]:
    return {key: str(value) for key, value in detail.items()}
