from functools import lru_cache

from apps.api.adapters.persistence.in_memory import (
    InMemoryAgentRunRepository,
    InMemoryAuditLog,
    InMemoryDocumentRepository,
)
from apps.api.adapters.vector.local_keyword import LocalKeywordVectorSearch
from apps.api.application.answering import GroundedAnswerSynthesizer
from apps.api.application.chunking import TextChunker
from apps.api.application.query_classifier import QueryClassifier
from apps.api.application.retrieval_strategy import RetrievalPlanner
from apps.api.application.use_cases import (
    IngestDocumentUseCase,
    RunAgentUseCase,
    SearchKnowledgeUseCase,
)
from apps.api.core.config import get_settings
from apps.api.domain.policies import AgentPolicy, RedactionPolicy


class AppContainer:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings

        self.documents = InMemoryDocumentRepository()
        self.audit_log = InMemoryAuditLog()
        self.runs = InMemoryAgentRunRepository()
        self.vector_search = LocalKeywordVectorSearch()

        self.chunker = TextChunker()
        self.classifier = QueryClassifier()
        self.planner = RetrievalPlanner()
        self.redaction_policy = RedactionPolicy()
        self.agent_policy = AgentPolicy()
        self.synthesizer = GroundedAnswerSynthesizer()

        self.ingest_document = IngestDocumentUseCase(
            documents=self.documents,
            vector_search=self.vector_search,
            audit_log=self.audit_log,
            chunker=self.chunker,
        )
        self.search_knowledge = SearchKnowledgeUseCase(
            vector_search=self.vector_search,
            audit_log=self.audit_log,
        )
        self.run_agent = RunAgentUseCase(
            vector_search=self.vector_search,
            audit_log=self.audit_log,
            runs=self.runs,
            classifier=self.classifier,
            planner=self.planner,
            redaction_policy=self.redaction_policy,
            agent_policy=self.agent_policy,
            synthesizer=self.synthesizer,
            default_top_k=settings.top_k,
        )


@lru_cache(maxsize=1)
def get_container() -> AppContainer:
    return AppContainer()
