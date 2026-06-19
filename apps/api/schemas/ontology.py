from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class OntologyNodeResponse(BaseModel):
    node_key: str
    label: str
    node_type: str
    source_document_id: UUID | None
    evidence_count: int
    metadata: dict[str, Any]


class OntologyEdgeResponse(BaseModel):
    source_key: str
    target_key: str
    relation: str
    evidence_count: int
    metadata: dict[str, Any]


class OntologyGraphResponse(BaseModel):
    tenant_id: str
    nodes: list[OntologyNodeResponse]
    edges: list[OntologyEdgeResponse]
    generated_at: datetime
