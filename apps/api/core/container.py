from functools import lru_cache

from apps.api.adapters.agent.local_tool_runtime import LocalToolRuntime
from apps.api.adapters.persistence.in_memory import (
    InMemoryAgentRunRepository,
    InMemoryApprovalRepository,
    InMemoryAuditLog,
    InMemoryDocumentRepository,
)
from apps.api.adapters.persistence.postgres import (
    PostgresAgentRunRepository,
    PostgresApprovalRepository,
    PostgresAuditLog,
    PostgresDocumentRepository,
)
from apps.api.adapters.vector.local_keyword import LocalKeywordVectorSearch
from apps.api.adapters.vector.qdrant import QdrantVectorSearch
from apps.api.application.answering import GroundedAnswerSynthesizer
from apps.api.application.chunking import TextChunker
from apps.api.application.ports import (
    AgentRunRepositoryPort,
    ApprovalRepositoryPort,
    AuditLogPort,
    DocumentRepositoryPort,
    VectorSearchPort,
)
from apps.api.application.query_classifier import QueryClassifier
from apps.api.application.retrieval_strategy import RetrievalPlanner
from apps.api.application.use_cases import (
    ApprovalUseCase,
    IngestDocumentUseCase,
    RunAgentUseCase,
    SearchKnowledgeUseCase,
)
from apps.api.core.config import get_settings
from apps.api.domain.policies import AgentPolicy, RedactionPolicy, ToolPolicy


class AppContainer:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.documents: DocumentRepositoryPort
        self.audit_log: AuditLogPort
        self.runs: AgentRunRepositoryPort
        self.approvals: ApprovalRepositoryPort
        self.vector_search: VectorSearchPort

        if settings.storage_backend == "postgres":
            self.documents = PostgresDocumentRepository(settings.postgres_dsn)
            self.audit_log = PostgresAuditLog(settings.postgres_dsn)
            self.runs = PostgresAgentRunRepository(settings.postgres_dsn)
            self.approvals = PostgresApprovalRepository(settings.postgres_dsn)
        else:
            self.documents = InMemoryDocumentRepository()
            self.audit_log = InMemoryAuditLog()
            self.runs = InMemoryAgentRunRepository()
            self.approvals = InMemoryApprovalRepository()

        if settings.vector_backend == "qdrant":
            self.vector_search = QdrantVectorSearch(
                url=settings.qdrant_url,
                collection_name=settings.qdrant_collection,
                dimensions=settings.embedding_dimensions,
            )
        else:
            self.vector_search = LocalKeywordVectorSearch()

        self.chunker = TextChunker()
        self.classifier = QueryClassifier()
        self.planner = RetrievalPlanner()
        self.redaction_policy = RedactionPolicy()
        self.agent_policy = AgentPolicy()
        self.tool_policy = ToolPolicy()
        self.tool_runtime = LocalToolRuntime(self.tool_policy)
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
            approvals=self.approvals,
            classifier=self.classifier,
            planner=self.planner,
            redaction_policy=self.redaction_policy,
            agent_policy=self.agent_policy,
            tool_runtime=self.tool_runtime,
            synthesizer=self.synthesizer,
            default_top_k=settings.top_k,
        )
        self.approval = ApprovalUseCase(
            approvals=self.approvals,
            tool_runtime=self.tool_runtime,
            audit_log=self.audit_log,
        )


@lru_cache(maxsize=1)
def get_container() -> AppContainer:
    return AppContainer()
