from __future__ import annotations

import hashlib
import math
import re

TOKEN_PATTERN = re.compile(r"[가-힣A-Za-z0-9+#./_-]+")


class HashEmbeddingProvider:
    """외부 API 없이 재현 가능한 sparse-to-dense 해시 임베딩."""

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in TOKEN_PATTERN.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]
