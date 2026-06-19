from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentScenarioStepResponse(BaseModel):
    id: str
    title: str
    message: str
    expected_query_type: str
    actor_scopes: list[str]
    min_confidence: float
    require_citation: bool
    require_approval: bool


class AgentScenarioResponse(BaseModel):
    id: str
    name: str
    description: str
    scenario: str
    tags: list[str]
    steps: list[AgentScenarioStepResponse]


class RunAgentScenarioRequest(BaseModel):
    tenant_id: str = "default"
    user_id: str = Field(default="operator-01", min_length=2)
    actor_scopes: list[str] = Field(default_factory=list)


class AgentScenarioStepResultResponse(BaseModel):
    step_id: str
    title: str
    run_id: UUID
    status: str
    query_type: str
    confidence: float
    citation_count: int
    tool_decision_counts: dict[str, int]
    passed: bool
    failed_checks: list[str]


class AgentScenarioRunResponse(BaseModel):
    id: UUID
    tenant_id: str
    scenario_id: str
    name: str
    status: str
    step_results: list[AgentScenarioStepResultResponse]
    metrics: dict[str, Any]
    generated_at: datetime
