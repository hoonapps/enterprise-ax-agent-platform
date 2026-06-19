from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from apps.api.core.container import AppContainer, get_container
from apps.api.core.idempotency import (
    IdempotencyKeyHeader,
    replay_idempotent_response,
    request_payload_hash,
    save_idempotent_response,
)
from apps.api.core.security import AuthPrincipal, require_scopes, require_tenant_access
from apps.api.domain.models import AgentRun, AgentRunTimelineItem, AuditEvent
from apps.api.schemas.agents import (
    AgentRunEvidenceBundleResponse,
    AgentRunFeedbackRequest,
    AgentRunFeedbackResponse,
    AgentRunPreviewResponse,
    AgentRunSummaryResponse,
    AgentRunTimelineItemResponse,
    RunAgentRequest,
    RunAgentResponse,
    SearchKnowledgeRequest,
    SearchKnowledgeResponse,
    SearchResultResponse,
)
from apps.api.schemas.common import (
    AuditEventResponse,
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
    require_tenant_access(auth, request.tenant_id)
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
    require_tenant_access(auth, request.tenant_id)
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


@router.post("/agents/runs/preview", response_model=AgentRunPreviewResponse)
def preview_agent_run(
    request: RunAgentRequest,
    container: ContainerDep,
    auth: AgentRunAuth,
) -> AgentRunPreviewResponse:
    require_tenant_access(auth, request.tenant_id)
    preview = container.run_agent.preview(
        tenant_id=request.tenant_id,
        scenario=request.scenario,
        message=request.message,
        actor_scopes=request.actor_scopes,
    )
    return AgentRunPreviewResponse(
        tenant_id=preview.tenant_id,
        scenario=preview.scenario,
        query_type=preview.query_type.value,
        redacted_query=preview.redacted_query,
        redaction_count=preview.redaction_count,
        retrieval_strategy=preview.retrieval_strategy,
        top_k=preview.top_k,
        policy=PolicyResponse(
            allowed=preview.policy_decision.allowed,
            decision=preview.policy_decision.decision,
            reason=preview.policy_decision.reason,
            redactions=preview.policy_decision.redactions,
        ),
        quota_allowed=preview.quota_allowed,
        quota_remaining=preview.quota_remaining,
        tool_name=preview.tool_name,
        tool_action_type=preview.tool_action_type.value if preview.tool_action_type else None,
        tool_risk_level=preview.tool_risk_level,
        tool_description=preview.tool_description,
        generated_at=preview.generated_at,
    )


@router.get("/agents/runs", response_model=list[AgentRunSummaryResponse])
def list_agent_runs(
    container: ContainerDep,
    auth: AgentReadAuth,
    tenant_id: str = "default",
    limit: int = Query(default=50, ge=1, le=200),
    scenario: str | None = None,
    status: str | None = None,
    query_type: str | None = None,
) -> list[AgentRunSummaryResponse]:
    require_tenant_access(auth, tenant_id)
    runs = container.run_agent.list_runs(
        tenant_id=tenant_id,
        limit=limit,
        scenario=scenario,
        status=status,
        query_type=query_type,
    )
    return [_to_summary_response(run) for run in runs]


@router.get("/agents/runs/{run_id}/timeline", response_model=list[AgentRunTimelineItemResponse])
def get_agent_run_timeline(
    run_id: UUID,
    container: ContainerDep,
    auth: AgentReadAuth,
    tenant_id: str = "default",
    audit_event_limit: int = Query(default=500, ge=1, le=2000),
) -> list[AgentRunTimelineItemResponse]:
    require_tenant_access(auth, tenant_id)
    timeline = container.run_agent.get_timeline(
        tenant_id=tenant_id,
        run_id=run_id,
        audit_event_limit=audit_event_limit,
    )
    if timeline is None:
        raise HTTPException(status_code=404, detail="Agent 실행 이력을 찾을 수 없습니다.")
    return [_to_timeline_response(item) for item in timeline]


@router.post("/agents/runs/{run_id}/feedback", response_model=AgentRunFeedbackResponse)
def submit_agent_run_feedback(
    run_id: UUID,
    request: AgentRunFeedbackRequest,
    container: ContainerDep,
    auth: AgentRunAuth,
) -> AgentRunFeedbackResponse:
    require_tenant_access(auth, request.tenant_id)
    feedback = container.agent_feedback.submit(
        tenant_id=request.tenant_id,
        run_id=run_id,
        rating=request.rating,
        outcome=request.outcome,
        submitted_by=request.submitted_by,
        comment=request.comment,
        tags=request.tags,
    )
    if feedback is None:
        raise HTTPException(status_code=404, detail="Agent 실행 이력을 찾을 수 없습니다.")
    return AgentRunFeedbackResponse(
        id=feedback.id,
        tenant_id=feedback.tenant_id,
        run_id=feedback.run_id,
        rating=feedback.rating,
        outcome=feedback.outcome,
        submitted_by=feedback.submitted_by,
        comment=feedback.comment,
        tags=feedback.tags,
        created_at=feedback.created_at,
    )


@router.get("/agents/runs/{run_id}/evidence", response_model=AgentRunEvidenceBundleResponse)
def get_agent_run_evidence_bundle(
    run_id: UUID,
    container: ContainerDep,
    auth: AgentReadAuth,
    tenant_id: str = "default",
    audit_event_limit: int = Query(default=500, ge=1, le=2000),
) -> AgentRunEvidenceBundleResponse:
    require_tenant_access(auth, tenant_id)
    bundle = container.run_agent.get_evidence_bundle(
        tenant_id=tenant_id,
        run_id=run_id,
        audit_event_limit=audit_event_limit,
    )
    if bundle is None:
        raise HTTPException(status_code=404, detail="Agent 실행 이력을 찾을 수 없습니다.")
    return AgentRunEvidenceBundleResponse(
        tenant_id=bundle.tenant_id,
        run_id=bundle.run_id,
        run=_to_response(bundle.run),
        timeline=[_to_timeline_response(item) for item in bundle.timeline],
        audit_events=[_to_audit_event_response(event) for event in bundle.audit_events],
        feedback_events=[_to_audit_event_response(event) for event in bundle.feedback_events],
        evidence_hash=bundle.evidence_hash,
        generated_at=bundle.generated_at,
    )


@router.get("/agents/runs/{run_id}", response_model=RunAgentResponse)
def get_agent_run(
    run_id: UUID,
    container: ContainerDep,
    auth: AgentReadAuth,
    tenant_id: str = "default",
) -> RunAgentResponse:
    require_tenant_access(auth, tenant_id)
    run = container.run_agent.get_run(tenant_id=tenant_id, run_id=run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent 실행 이력을 찾을 수 없습니다.")
    return _to_response(run)


def _to_summary_response(run: AgentRun) -> AgentRunSummaryResponse:
    preview = " ".join(run.redacted_query.split())
    if len(preview) > 120:
        preview = f"{preview[:117]}..."
    return AgentRunSummaryResponse(
        run_id=run.id,
        tenant_id=run.tenant_id,
        scenario=run.scenario,
        status=run.status.value,
        query_type=run.query_type.value,
        redacted_query_preview=preview,
        confidence=run.confidence,
        citation_count=len(run.citations),
        tool_execution_count=len(run.tool_executions),
        trace_step_count=len(run.trace),
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


def _to_timeline_response(item: AgentRunTimelineItem) -> AgentRunTimelineItemResponse:
    return AgentRunTimelineItemResponse(
        run_id=item.run_id,
        source=item.source,
        event_type=item.event_type,
        status=item.status,
        title=item.title,
        detail=item.detail,
        sequence=item.sequence,
        occurred_at=item.occurred_at,
    )


def _to_audit_event_response(event: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse(
        id=event.id,
        tenant_id=event.tenant_id,
        actor_type=event.actor_type,
        actor_id=event.actor_id,
        event_type=event.event_type,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        payload=event.payload,
        created_at=event.created_at,
    )


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
