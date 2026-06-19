from typing import Annotated

from fastapi import APIRouter, Depends

from apps.api.core.container import AppContainer, get_container
from apps.api.core.idempotency import (
    IdempotencyKeyHeader,
    replay_idempotent_response,
    request_payload_hash,
    save_idempotent_response,
)
from apps.api.core.security import AuthPrincipal, require_scopes, require_tenant_access
from apps.api.domain.models import Classification, Document
from apps.api.schemas.documents import (
    DocumentResponse,
    IngestDocumentRequest,
    IngestDocumentResponse,
)

router = APIRouter(prefix="/v1/documents", tags=["documents"])
ContainerDep = Annotated[AppContainer, Depends(get_container)]
DocumentReadAuth = Annotated[AuthPrincipal, Depends(require_scopes("documents:read"))]
DocumentWriteAuth = Annotated[AuthPrincipal, Depends(require_scopes("documents:write"))]


@router.post("/ingest", response_model=IngestDocumentResponse)
def ingest_document(
    request: IngestDocumentRequest,
    container: ContainerDep,
    auth: DocumentWriteAuth,
    idempotency_key: IdempotencyKeyHeader = None,
) -> IngestDocumentResponse:
    require_tenant_access(auth, request.tenant_id)
    request_hash = request_payload_hash(request)
    replayed = replay_idempotent_response(
        repository=container.idempotency,
        tenant_id=request.tenant_id,
        key=idempotency_key,
        request_hash=request_hash,
        response_type=IngestDocumentResponse,
    )
    if replayed is not None:
        return replayed

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
    response = IngestDocumentResponse(
        document_id=saved.id,
        tenant_id=saved.tenant_id,
        title=saved.title,
        chunk_count=chunk_count,
        classification=saved.classification.value,
    )
    save_idempotent_response(
        repository=container.idempotency,
        tenant_id=request.tenant_id,
        key=idempotency_key,
        request_hash=request_hash,
        response=response,
    )
    return response


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    container: ContainerDep,
    auth: DocumentReadAuth,
    tenant_id: str = "default",
) -> list[DocumentResponse]:
    require_tenant_access(auth, tenant_id)
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
