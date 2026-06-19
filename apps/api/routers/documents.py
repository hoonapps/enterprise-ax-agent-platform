from typing import Annotated

from fastapi import APIRouter, Depends

from apps.api.core.container import AppContainer, get_container
from apps.api.domain.models import Classification, Document
from apps.api.schemas.documents import (
    DocumentResponse,
    IngestDocumentRequest,
    IngestDocumentResponse,
)

router = APIRouter(prefix="/v1/documents", tags=["documents"])
ContainerDep = Annotated[AppContainer, Depends(get_container)]


@router.post("/ingest", response_model=IngestDocumentResponse)
def ingest_document(
    request: IngestDocumentRequest,
    container: ContainerDep,
) -> IngestDocumentResponse:
    document = Document(
        tenant_id=request.tenant_id,
        title=request.title,
        content=request.content,
        source_type=request.source_type,
        source_uri=request.source_uri,
        classification=Classification(request.classification),
        metadata=request.metadata,
    )
    saved, chunk_count = container.ingest_document.execute(document=document)
    return IngestDocumentResponse(
        document_id=saved.id,
        tenant_id=saved.tenant_id,
        title=saved.title,
        chunk_count=chunk_count,
        classification=saved.classification.value,
    )


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    container: ContainerDep,
    tenant_id: str = "default",
) -> list[DocumentResponse]:
    return [
        DocumentResponse(
            id=document.id,
            tenant_id=document.tenant_id,
            title=document.title,
            source_type=document.source_type,
            source_uri=document.source_uri,
            classification=document.classification.value,
            metadata=document.metadata,
        )
        for document in container.documents.list_documents(tenant_id)
    ]
