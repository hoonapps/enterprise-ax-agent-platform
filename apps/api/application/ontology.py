from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from apps.api.domain.models import Document, OntologyEdge, OntologyNode


@dataclass(frozen=True)
class ExtractedOntology:
    nodes: list[OntologyNode]
    edges: list[OntologyEdge]


class OntologyExtractor:
    _term_pattern = re.compile(r"[A-Za-z][A-Za-z0-9_.+#/-]{2,}|[가-힣][가-힣A-Za-z0-9_.+#/-]{1,}")
    _stopwords = {
        "그리고",
        "또는",
        "위해",
        "대한",
        "에서",
        "으로",
        "하는",
        "한다",
        "있다",
        "없다",
        "기반",
        "포함",
        "운영",
        "문서",
        "요청",
        "시스템",
        "agent",
        "api",
        "the",
        "and",
        "for",
        "with",
        "that",
    }

    def extract(self, document: Document, max_terms: int = 24) -> ExtractedOntology:
        document_node = OntologyNode(
            tenant_id=document.tenant_id,
            node_key=f"document:{document.id}",
            label=document.title,
            node_type="document",
            source_document_id=document.id,
            metadata={
                "source_type": document.source_type,
                "source_uri": document.source_uri,
            },
        )
        classification_node = OntologyNode(
            tenant_id=document.tenant_id,
            node_key=f"classification:{document.classification.value}",
            label=document.classification.value,
            node_type="classification",
            metadata={"classification": document.classification.value},
        )

        metadata_nodes = self._metadata_nodes(document)
        concept_nodes = self._concept_nodes(document, max_terms=max_terms)
        nodes = [document_node, classification_node, *metadata_nodes, *concept_nodes]
        edges = [
            OntologyEdge(
                tenant_id=document.tenant_id,
                source_key=document_node.node_key,
                target_key=classification_node.node_key,
                relation="classified_as",
            )
        ]
        edges.extend(
            OntologyEdge(
                tenant_id=document.tenant_id,
                source_key=document_node.node_key,
                target_key=node.node_key,
                relation="has_metadata",
            )
            for node in metadata_nodes
        )
        edges.extend(
            OntologyEdge(
                tenant_id=document.tenant_id,
                source_key=document_node.node_key,
                target_key=node.node_key,
                relation="mentions",
                evidence_count=node.evidence_count,
            )
            for node in concept_nodes
        )
        edges.extend(self._co_occurrence_edges(document.tenant_id, concept_nodes))
        return ExtractedOntology(nodes=nodes, edges=edges)

    def _metadata_nodes(self, document: Document) -> list[OntologyNode]:
        nodes: list[OntologyNode] = []
        for key, value in sorted(document.metadata.items()):
            for item in self._metadata_values(value):
                node_key = f"metadata:{self._normalize_key(key)}:{self._normalize_key(item)}"
                nodes.append(
                    OntologyNode(
                        tenant_id=document.tenant_id,
                        node_key=node_key,
                        label=item,
                        node_type=f"metadata:{key}",
                        source_document_id=document.id,
                        metadata={"metadata_key": key},
                    )
                )
        return nodes[:12]

    def _metadata_values(self, value: Any) -> list[str]:
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    def _concept_nodes(self, document: Document, max_terms: int) -> list[OntologyNode]:
        text = f"{document.title}\n{document.content}"
        terms = [
            term.strip("._-/+#").lower()
            for term in self._term_pattern.findall(text)
            if self._is_candidate(term)
        ]
        counts = Counter(terms)
        nodes: list[OntologyNode] = []
        for term, count in counts.most_common(max_terms):
            nodes.append(
                OntologyNode(
                    tenant_id=document.tenant_id,
                    node_key=f"concept:{self._normalize_key(term)}",
                    label=term,
                    node_type="concept",
                    source_document_id=document.id,
                    evidence_count=count,
                    metadata={"source_uri": document.source_uri},
                )
            )
        return nodes

    def _is_candidate(self, term: str) -> bool:
        normalized = term.strip("._-/+#").lower()
        if len(normalized) < 2:
            return False
        return normalized not in self._stopwords

    def _co_occurrence_edges(
        self,
        tenant_id: str,
        concept_nodes: list[OntologyNode],
    ) -> list[OntologyEdge]:
        top_nodes = concept_nodes[:8]
        edges: list[OntologyEdge] = []
        for index, source in enumerate(top_nodes):
            for target in top_nodes[index + 1 : index + 3]:
                edges.append(
                    OntologyEdge(
                        tenant_id=tenant_id,
                        source_key=source.node_key,
                        target_key=target.node_key,
                        relation="co_occurs_with",
                        evidence_count=min(source.evidence_count, target.evidence_count),
                    )
                )
        return edges

    def _normalize_key(self, value: str) -> str:
        normalized = re.sub(r"[^0-9a-zA-Z가-힣]+", "-", value.strip().lower())
        return normalized.strip("-") or "unknown"
