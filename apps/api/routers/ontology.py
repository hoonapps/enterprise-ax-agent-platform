from typing import Annotated

from fastapi import APIRouter, Depends

from apps.api.core.container import AppContainer, get_container
from apps.api.core.security import AuthPrincipal, require_scopes, require_tenant_access
from apps.api.domain.models import OntologyEdge, OntologyGraph, OntologyNode
from apps.api.schemas.ontology import (
    OntologyEdgeResponse,
    OntologyGraphResponse,
    OntologyNodeResponse,
)

router = APIRouter(prefix="/v1/ontology", tags=["ontology"])
ContainerDep = Annotated[AppContainer, Depends(get_container)]
OntologyReadAuth = Annotated[AuthPrincipal, Depends(require_scopes("ontology:read"))]


@router.get("/graph", response_model=OntologyGraphResponse)
def get_ontology_graph(
    container: ContainerDep,
    auth: OntologyReadAuth,
    tenant_id: str = "default",
    limit: int = 200,
) -> OntologyGraphResponse:
    require_tenant_access(auth, tenant_id)
    graph = container.ontology.get_graph(tenant_id=tenant_id, limit=limit)
    return _to_response(graph)


def _to_response(graph: OntologyGraph) -> OntologyGraphResponse:
    return OntologyGraphResponse(
        tenant_id=graph.tenant_id,
        nodes=[_node_to_response(node) for node in graph.nodes],
        edges=[_edge_to_response(edge) for edge in graph.edges],
        generated_at=graph.generated_at,
    )


def _node_to_response(node: OntologyNode) -> OntologyNodeResponse:
    return OntologyNodeResponse(
        node_key=node.node_key,
        label=node.label,
        node_type=node.node_type,
        source_document_id=node.source_document_id,
        evidence_count=node.evidence_count,
        metadata=node.metadata,
    )


def _edge_to_response(edge: OntologyEdge) -> OntologyEdgeResponse:
    return OntologyEdgeResponse(
        source_key=edge.source_key,
        target_key=edge.target_key,
        relation=edge.relation,
        evidence_count=edge.evidence_count,
        metadata=edge.metadata,
    )
