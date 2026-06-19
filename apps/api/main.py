from fastapi import FastAPI

from apps.api.routers import agents, audit, documents, health


def create_app() -> FastAPI:
    app = FastAPI(
        title="Enterprise AX Agent Platform",
        description=(
            "한국 대기업 AX/AI Agent Engineer 포트폴리오를 위한 "
            "FastAPI 기반 기업형 Agent 백엔드"
        ),
        version="0.1.0",
    )
    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(agents.router)
    app.include_router(audit.router)
    return app


app = create_app()
