from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http import models

from apps.api.adapters.vector.embedding import HashEmbeddingProvider
from apps.api.domain.models import Classification, DocumentChunk, RetrievalResult


class QdrantVectorSearch:
    def __init__(self, *, url: str, collection_name: str, dimensions: int) -> None:
        self.client = QdrantClient(url=url)
        self.collection_name = collection_name
        self.embedding = HashEmbeddingProvider(dimensions=dimensions)
        self.dimensions = dimensions
        self._ensure_collection()

    def upsert(self, chunks: list[DocumentChunk]) -> None:
        if not chunks:
            return

        points = [
            models.PointStruct(
                id=str(chunk.id),
                vector=self.embedding.embed(chunk.content + " " + chunk.title),
                payload={
                    "tenant_id": chunk.tenant_id,
                    "document_id": str(chunk.document_id),
                    "chunk_id": str(chunk.id),
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "title": chunk.title,
                    "source_uri": chunk.source_uri,
                    "classification": chunk.classification.value,
                    "metadata": chunk.metadata,
                },
            )
            for chunk in chunks
        ]
        self.client.upsert(collection_name=self.collection_name, points=points)

    def search(self, tenant_id: str, query: str, top_k: int) -> list[RetrievalResult]:
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=self.embedding.embed(query),
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="tenant_id",
                        match=models.MatchValue(value=tenant_id),
                    )
                ]
            ),
            limit=top_k,
            with_payload=True,
        )
        points = cast(list[Any], response.points)
        return [self._point_to_result(point) for point in points if point.payload]

    def _ensure_collection(self) -> None:
        if self.client.collection_exists(self.collection_name):
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=self.dimensions,
                distance=models.Distance.COSINE,
            ),
        )

    def _point_to_result(self, point: Any) -> RetrievalResult:
        payload = cast(dict[str, Any], point.payload)
        chunk = DocumentChunk(
            id=UUID(str(payload["chunk_id"])),
            tenant_id=str(payload["tenant_id"]),
            document_id=UUID(str(payload["document_id"])),
            chunk_index=int(payload["chunk_index"]),
            content=str(payload["content"]),
            title=str(payload["title"]),
            source_uri=str(payload["source_uri"]),
            classification=Classification(str(payload["classification"])),
            metadata=cast(dict[str, Any], payload.get("metadata", {})),
        )
        return RetrievalResult(chunk=chunk, score=float(point.score or 0.0))
