from __future__ import annotations

from apps.api.domain.models import Document, DocumentChunk


class TextChunker:
    def __init__(self, max_chars: int = 900, overlap: int = 120) -> None:
        self.max_chars = max_chars
        self.overlap = overlap

    def split(self, document: Document) -> list[DocumentChunk]:
        normalized = "\n".join(
            line.strip() for line in document.content.splitlines() if line.strip()
        )
        if not normalized:
            return []

        chunks: list[DocumentChunk] = []
        start = 0
        index = 0
        while start < len(normalized):
            end = min(start + self.max_chars, len(normalized))
            content = normalized[start:end].strip()
            if content:
                chunks.append(
                    DocumentChunk(
                        tenant_id=document.tenant_id,
                        document_id=document.id,
                        chunk_index=index,
                        content=content,
                        title=document.title,
                        source_uri=document.source_uri,
                        classification=document.classification,
                        metadata=document.metadata,
                    )
                )
                index += 1
            if end == len(normalized):
                break
            start = max(end - self.overlap, start + 1)
        return chunks
