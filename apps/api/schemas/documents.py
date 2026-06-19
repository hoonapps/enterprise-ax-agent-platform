from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class IngestDocumentRequest(BaseModel):
    tenant_id: str = "default"
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=20)
    source_type: str = "manual"
    source_uri: str = "local"
    classification: str = "internal"
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestDocumentResponse(BaseModel):
    document_id: UUID
    tenant_id: str
    title: str
    chunk_count: int
    classification: str


class DocumentResponse(BaseModel):
    id: UUID
    tenant_id: str
    title: str
    source_type: str
    source_uri: str
    classification: str
    metadata: dict[str, Any]
