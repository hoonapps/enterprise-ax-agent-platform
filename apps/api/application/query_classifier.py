from apps.api.domain.models import QueryType


class QueryClassifier:
    def classify(self, message: str) -> QueryType:
        lowered = message.lower()
        if any(keyword in lowered for keyword in ("비교", "compare", "차이", "versus", "vs")):
            return QueryType.COMPARE
        if any(keyword in lowered for keyword in ("요약", "summary", "summarize", "정리")):
            return QueryType.SUMMARY
        if any(keyword in lowered for keyword in ("실행", "처리", "보내", "생성", "run", "create")):
            return QueryType.ACTION
        if any(keyword in lowered for keyword in ("리스크", "risk", "보안", "거버넌스", "장애")):
            return QueryType.RISK
        return QueryType.FACTUAL
