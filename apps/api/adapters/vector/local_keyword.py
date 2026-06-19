from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

from apps.api.domain.models import DocumentChunk, RetrievalResult

TOKEN_PATTERN = re.compile(r"[가-힣A-Za-z0-9+#./_-]+")


class LocalKeywordVectorSearch:
    """외부 Vector DB 없이 MVP를 검증하기 위한 deterministic 검색 어댑터."""

    def __init__(self) -> None:
        self._chunks: dict[str, list[DocumentChunk]] = defaultdict(list)

    def upsert(self, chunks: list[DocumentChunk]) -> None:
        for chunk in chunks:
            tenant_chunks = self._chunks[chunk.tenant_id]
            existing_index = next(
                (idx for idx, item in enumerate(tenant_chunks) if item.id == chunk.id),
                None,
            )
            if existing_index is None:
                tenant_chunks.append(chunk)
            else:
                tenant_chunks[existing_index] = chunk

    def search(self, tenant_id: str, query: str, top_k: int) -> list[RetrievalResult]:
        query_vector = self._vectorize(query)
        if not query_vector:
            return []

        scored: list[RetrievalResult] = []
        for chunk in self._chunks[tenant_id]:
            score = self._cosine(query_vector, self._vectorize(chunk.content + " " + chunk.title))
            if score > 0:
                scored.append(RetrievalResult(chunk=chunk, score=score))

        scored.sort(key=lambda result: result.score, reverse=True)
        return scored[:top_k]

    def _vectorize(self, text: str) -> Counter[str]:
        tokens = [token.lower() for token in TOKEN_PATTERN.findall(text)]
        expanded: list[str] = []
        for token in tokens:
            expanded.append(token)
            if len(token) >= 4:
                expanded.extend(token[idx : idx + 2] for idx in range(0, len(token) - 1))
        return Counter(expanded)

    def _cosine(self, left: Counter[str], right: Counter[str]) -> float:
        common = set(left) & set(right)
        numerator = sum(left[token] * right[token] for token in common)
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)
