from dataclasses import dataclass

from apps.api.domain.models import QueryType


@dataclass(frozen=True)
class RetrievalPlan:
    strategy: str
    top_k: int
    include_policy_context: bool = False
    allow_tools: bool = False


class RetrievalPlanner:
    def plan(self, query_type: QueryType, default_top_k: int) -> RetrievalPlan:
        if query_type == QueryType.SUMMARY:
            return RetrievalPlan(strategy="broad-summary", top_k=max(default_top_k, 6))
        if query_type == QueryType.COMPARE:
            return RetrievalPlan(strategy="multi-source-compare", top_k=max(default_top_k, 6))
        if query_type == QueryType.ACTION:
            return RetrievalPlan(strategy="action-grounding", top_k=default_top_k, allow_tools=True)
        if query_type == QueryType.RISK:
            return RetrievalPlan(
                strategy="risk-and-governance",
                top_k=max(default_top_k, 5),
                include_policy_context=True,
            )
        return RetrievalPlan(strategy="precise-factual", top_k=default_top_k)
