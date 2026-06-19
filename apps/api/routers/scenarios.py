from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from apps.api.core.container import AppContainer, get_container
from apps.api.core.security import AuthPrincipal, require_scopes, require_tenant_access
from apps.api.domain.models import (
    AgentScenarioDefinition,
    AgentScenarioRunResult,
    AgentScenarioStep,
    AgentScenarioStepResult,
)
from apps.api.schemas.scenarios import (
    AgentScenarioResponse,
    AgentScenarioRunResponse,
    AgentScenarioStepResponse,
    AgentScenarioStepResultResponse,
    RunAgentScenarioRequest,
)

router = APIRouter(prefix="/v1/scenarios", tags=["scenarios"])
ContainerDep = Annotated[AppContainer, Depends(get_container)]
ScenarioReadAuth = Annotated[AuthPrincipal, Depends(require_scopes("agents:read"))]
ScenarioRunAuth = Annotated[AuthPrincipal, Depends(require_scopes("agents:run"))]


@router.get("", response_model=list[AgentScenarioResponse])
def list_agent_scenarios(
    container: ContainerDep,
    _auth: ScenarioReadAuth,
) -> list[AgentScenarioResponse]:
    return [
        _to_scenario_response(scenario)
        for scenario in container.agent_scenarios.list_scenarios()
    ]


@router.get("/{scenario_id}", response_model=AgentScenarioResponse)
def get_agent_scenario(
    scenario_id: str,
    container: ContainerDep,
    _auth: ScenarioReadAuth,
) -> AgentScenarioResponse:
    scenario = container.agent_scenarios.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Agent scenario를 찾을 수 없습니다.")
    return _to_scenario_response(scenario)


@router.post("/{scenario_id}/run", response_model=AgentScenarioRunResponse)
def run_agent_scenario(
    scenario_id: str,
    request: RunAgentScenarioRequest,
    container: ContainerDep,
    auth: ScenarioRunAuth,
) -> AgentScenarioRunResponse:
    require_tenant_access(auth, request.tenant_id)
    result = container.agent_scenarios.execute(
        tenant_id=request.tenant_id,
        scenario_id=scenario_id,
        user_id=request.user_id,
        actor_scopes=request.actor_scopes,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Agent scenario를 찾을 수 없습니다.")
    return _to_run_response(result)


def _to_scenario_response(scenario: AgentScenarioDefinition) -> AgentScenarioResponse:
    return AgentScenarioResponse(
        id=scenario.id,
        name=scenario.name,
        description=scenario.description,
        scenario=scenario.scenario,
        tags=scenario.tags,
        steps=[_to_step_response(step) for step in scenario.steps],
    )


def _to_step_response(step: AgentScenarioStep) -> AgentScenarioStepResponse:
    return AgentScenarioStepResponse(
        id=step.id,
        title=step.title,
        message=step.message,
        expected_query_type=step.expected_query_type.value,
        actor_scopes=step.actor_scopes,
        min_confidence=step.min_confidence,
        require_citation=step.require_citation,
        require_approval=step.require_approval,
    )


def _to_run_response(result: AgentScenarioRunResult) -> AgentScenarioRunResponse:
    return AgentScenarioRunResponse(
        id=result.id,
        tenant_id=result.tenant_id,
        scenario_id=result.scenario_id,
        name=result.name,
        status=result.status,
        step_results=[_to_step_result_response(step) for step in result.step_results],
        metrics=result.metrics,
        generated_at=result.generated_at,
    )


def _to_step_result_response(
    step: AgentScenarioStepResult,
) -> AgentScenarioStepResultResponse:
    return AgentScenarioStepResultResponse(
        step_id=step.step_id,
        title=step.title,
        run_id=step.run_id,
        status=step.status,
        query_type=step.query_type,
        confidence=step.confidence,
        citation_count=step.citation_count,
        tool_decision_counts=step.tool_decision_counts,
        passed=step.passed,
        failed_checks=step.failed_checks,
    )
