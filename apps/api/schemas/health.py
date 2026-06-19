from pydantic import BaseModel, Field


class DependencyCheckResponse(BaseModel):
    name: str
    status: str
    latency_ms: int = Field(ge=0)
    detail: dict[str, str] = Field(default_factory=dict)


class ReadinessResponse(BaseModel):
    status: str
    environment: str
    llm_mode: str
    storage_backend: str
    vector_backend: str
    auth_mode: str
    dependencies: list[DependencyCheckResponse]
