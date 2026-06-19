from fastapi import APIRouter

from apps.api.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": get_settings().app_name}


@router.get("/v1/readiness")
def readiness() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ready",
        "environment": settings.app_env,
        "llm_mode": settings.llm_mode,
        "storage_backend": settings.storage_backend,
        "vector_backend": settings.vector_backend,
    }
