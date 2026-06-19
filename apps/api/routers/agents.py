from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from apps.api.core.container import AppContainer, get_container
from apps.api.core.idempotency import (
    IdempotencyKeyHeader,
    replay_idempotent_response,
    request_payload_hash,
    save_idempotent_response,
)
from apps.api.core.security import AuthPrincipal, require_scopes
from apps.api.domain.models import AgentRun
from apps.api.schemas.agents import (
    RunAgentRequest,
    RunAgentResponse,
    SearchKnowledgeRequest,
    SearchKnowledgeResponse,
    SearchResultResponse,
)
from apps.api.schemas.common import (
    CitationResponse,
    PolicyResponse,
    ToolExecutionResponse,
    TraceStepResponse,
)

router = APIRouter(prefix="/v1", tags=["agents"])
ContainerDep = Annotated[AppContainer, Depends(get_container)]
KnowledgeReadAuth = Annotated[AuthPrincipal, Depends(require_scopes("knowledge:read"))]
AgentReadAuth = Annotated[AuthPrincipal, Depends(require_scopes("agents:read"))]
AgentRunAuth = Annotated[AuthPrincipal, Depends(require_scopes("agents:run"))]


@router.post("/knowledge/search", response_model=SearchKnowledgeResponse)
def search_knowledge(
    request: SearchKnowledgeRequest,
    container: ContainerDep,
    auth: KnowledgeReadAuth,
) -> SearchKnowledgeResponse:
    results = container.search_knowledge.execute(
        tenant_id=request.tenant_id,
        query=request.query,
        top_k=request.top_k,
    )
    return SearchKnowledgeResponse(
        results=[
            SearchResultResponse(
                document_id=result.chunk.document_id,
                chunk_id=result.chunk.id,
                title=result.chunk.title,
                source_uri=result.chunk.source_uri,
                score=round(result.score, 4),
                content=result.chunk.content,
            )
            for result in results
        ]
    )


@router.post("/agents/runs", response_model=RunAgentResponse)
def run_agent(
    request: RunAgentRequest,
    container: ContainerDep,
    auth: AgentRunAuth,
    idempotency_key: IdempotencyKeyHeader = None,
) -> RunAgentResponse:
    request_hash = request_payload_hash(request)
    replayed = replay_idempotent_response(
        repository=container.idempotency,
        tenant_id=request.tenant_id,
        key=idempotency_key,
        request_hash=request_hash,
        response_type=RunAgentResponse,
    )
    if replayed is not None:
        return replayed

    run = container.run_agent.execute(
        tenant_id=request.tenant_id,
        scenario=request.scenario,
        message=request.message,
        user_id=request.user_id,
        actor_scopes=request.actor_scopes,
    )
    response = _to_response(run)
    save_idempotent_response(
        repository=container.idempotency,
        tenant_id=request.tenant_id,
        key=idempotency_key,
        request_hash=request_hash,
        response=response,
    )
    return response


@router.get("/agents/runs/{run_id}", response_model=RunAgentResponse)
def get_agent_run(
    run_id: UUID,
    container: ContainerDep,
    auth: AgentReadAuth,
    tenant_id: str = "default",
) -> RunAgentResponse:
    run = container.run_agent.get_run(tenant_id=tenant_id, run_id=run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent 실행 이력을 찾을 수 없습니다.")
    return _to_response(run)


def _to_response(run: AgentRun) -> RunAgentResponse:
    return RunAgentResponse(
        run_id=run.id,
        tenant_id=run.tenant_id,
        scenario=run.scenario,
        status=run.status.value,
        query_type=run.query_type.value,
        answer=run.answer,
        confidence=run.confidence,
        citations=[
            CitationResponse(
                document_id=citation.document_id,
                chunk_id=citation.chunk_id,
                title=citation.title,
                score=citation.score,
                source_uri=citation.source_uri,
            )
            for citation in run.citations
        ],
        trace=[
            TraceStepResponse(step=step.step, status=step.status, detail=step.detail)
            for step in run.trace
        ],
        policy=PolicyResponse(
            allowed=run.policy_decision.allowed,
            decision=run.policy_decision.decision,
            reason=run.policy_decision.reason,
            redactions=run.policy_decision.redactions,
        ),
        tool_executions=[
            ToolExecutionResponse(
                id=execution.id,
                tool_name=execution.tool_name,
                action_type=execution.action_type.value,
                decision=execution.decision.value,
                status=execution.status,
                reason=execution.reason,
                input_payload=execution.input_payload,
                output_payload=execution.output_payload,
            )
            for execution in run.tool_executions
        ],
    )
