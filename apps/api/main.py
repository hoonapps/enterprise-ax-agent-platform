from fastapi import FastAPI

from apps.api.core.observability import RequestContextMiddleware
from apps.api.routers import (
    agents,
    approvals,
    audit,
    dashboard,
    documents,
    evaluations,
    health,
    mcp,
    ontology,
    operations,
    tools,
    webhooks,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Enterprise AX Agent Platform",
        description=(
            "사내 지식 검색, 업무 자동화, 정책 감사, 운영 추적을 위한 "
            "FastAPI 기반 AX Agent 백엔드"
        ),
        version="0.1.0",
    )
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health.router)
    app.include_router(dashboard.router)
    app.include_router(documents.router)
    app.include_router(agents.router)
    app.include_router(evaluations.router)
    app.include_router(ontology.router)
    app.include_router(operations.router)
    app.include_router(approvals.router)
    app.include_router(tools.router)
    app.include_router(webhooks.router)
    app.include_router(mcp.router)
    app.include_router(audit.router)
    return app


app = create_app()
