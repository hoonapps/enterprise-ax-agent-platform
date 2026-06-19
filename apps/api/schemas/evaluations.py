from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EvaluationCaseRequest(BaseModel):
    input_query: str = Field(..., min_length=2)
    expected_facts: list[str] = Field(default_factory=list)


class RunEvaluationRequest(BaseModel):
    tenant_id: str = "default"
    name: str = Field(..., min_length=2, max_length=120)
    scenario: str = Field(default="operations", min_length=2)
    cases: list[EvaluationCaseRequest] = Field(..., min_length=1, max_length=50)


class EvaluationCaseResponse(BaseModel):
    id: UUID
    input_query: str
    expected_facts: list[str]
    actual_answer: str
    score: float
    failure_reason: str | None


class EvaluationRunResponse(BaseModel):
    id: UUID
    tenant_id: str
    name: str
    scenario: str
    status: str
    metrics: dict[str, Any]
    cases: list[EvaluationCaseResponse]
    created_at: datetime
    completed_at: datetime | None
