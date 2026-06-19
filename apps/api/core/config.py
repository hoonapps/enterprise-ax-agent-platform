from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Enterprise AX Agent Platform"
    app_env: str = "local"
    log_level: str = "INFO"

    runtime_dir: Path = Path("data/runtime")
    sample_docs_dir: Path = Path("data/sample_docs")
    embedding_dimensions: int = Field(default=384, ge=32, le=3072)
    top_k: int = Field(default=4, ge=1, le=20)
    storage_backend: str = "memory"
    vector_backend: str = "local"

    openai_api_key: str = ""
    anthropic_api_key: str = ""

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "ax_agent_chunks"
    postgres_dsn: str = "postgresql://ax_agent:ax_agent@localhost:5432/ax_agent"

    @property
    def llm_mode(self) -> str:
        if self.openai_api_key:
            return "openai-ready"
        if self.anthropic_api_key:
            return "anthropic-ready"
        return "deterministic-local"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
