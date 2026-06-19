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
from apps.api.domain.models import EvaluationCase, EvaluationRun
from apps.api.schemas.evaluations import (
    EvaluationCaseResponse,
    EvaluationRunResponse,
    RunEvaluationRequest,
)

router = APIRouter(prefix="/v1/evaluations", tags=["evaluations"])
ContainerDep = Annotated[AppContainer, Depends(get_container)]
EvaluationReadAuth = Annotated[AuthPrincipal, Depends(require_scopes("evaluations:read"))]
EvaluationWriteAuth = Annotated[AuthPrincipal, Depends(require_scopes("evaluations:write"))]


@router.post("/runs", response_model=EvaluationRunResponse)
def run_evaluation(
    request: RunEvaluationRequest,
    container: ContainerDep,
    auth: EvaluationWriteAuth,
    idempotency_key: IdempotencyKeyHeader = None,
) -> EvaluationRunResponse:
    request_hash = request_payload_hash(request)
    replayed = replay_idempotent_response(
        repository=container.idempotency,
        tenant_id=request.tenant_id,
        key=idempotency_key,
        request_hash=request_hash,
        response_type=EvaluationRunResponse,
    )
    if replayed is not None:
        return replayed

    cases = [
        EvaluationCase(
            tenant_id=request.tenant_id,
            evaluation_run_id=UUID("00000000-0000-0000-0000-000000000000"),
            input_query=case.input_query,
            expected_facts=case.expected_facts,
        )
        for case in request.cases
    ]
    run = container.evaluate_agent.execute(
        tenant_id=request.tenant_id,
        name=request.name,
        scenario=request.scenario,
        cases=cases,
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


@router.get("/runs/{evaluation_run_id}", response_model=EvaluationRunResponse)
def get_evaluation_run(
    evaluation_run_id: UUID,
    container: ContainerDep,
    auth: EvaluationReadAuth,
    tenant_id: str = "default",
) -> EvaluationRunResponse:
    run = container.evaluate_agent.get(
        tenant_id=tenant_id,
        evaluation_run_id=evaluation_run_id,
    )
    if run is None:
        raise HTTPException(status_code=404, detail="평가 실행을 찾을 수 없습니다.")
    return _to_response(run)


def _to_response(run: EvaluationRun) -> EvaluationRunResponse:
    return EvaluationRunResponse(
        id=run.id,
        tenant_id=run.tenant_id,
        name=run.name,
        scenario=run.scenario,
        status=run.status.value,
        metrics=run.metrics,
        cases=[
            EvaluationCaseResponse(
                id=case.id,
                input_query=case.input_query,
                expected_facts=case.expected_facts,
                actual_answer=case.actual_answer,
                score=case.score,
                failure_reason=case.failure_reason,
            )
            for case in run.cases
        ],
        created_at=run.created_at,
        completed_at=run.completed_at,
    )
