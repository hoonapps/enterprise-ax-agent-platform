from functools import lru_cache

from apps.api.adapters.agent.local_tool_gateway import LocalToolGateway
from apps.api.adapters.agent.local_tool_registry import LocalToolRegistry
from apps.api.adapters.agent.local_tool_runtime import LocalToolRuntime
from apps.api.adapters.agent.resilient_tool_gateway import ResilientToolGateway
from apps.api.adapters.persistence.audit_context import RequestContextAuditLog
from apps.api.adapters.persistence.in_memory import (
    InMemoryAgentRunRepository,
    InMemoryApprovalRepository,
    InMemoryAuditLog,
    InMemoryDocumentRepository,
    InMemoryEvaluationRepository,
    InMemoryIdempotencyRepository,
    InMemoryOntologyRepository,
    InMemoryWebhookDeliveryRepository,
    InMemoryWebhookSubscriptionRepository,
)
from apps.api.adapters.persistence.outbox import OutboxAuditLog
from apps.api.adapters.persistence.postgres import (
    PostgresAgentRunRepository,
    PostgresApprovalRepository,
    PostgresAuditLog,
    PostgresDocumentRepository,
    PostgresEvaluationRepository,
    PostgresIdempotencyRepository,
    PostgresOntologyRepository,
    PostgresWebhookDeliveryRepository,
    PostgresWebhookSubscriptionRepository,
)
from apps.api.adapters.vector.local_keyword import LocalKeywordVectorSearch
from apps.api.adapters.vector.qdrant import QdrantVectorSearch
from apps.api.adapters.webhook_http import UrllibWebhookHttpClient
from apps.api.application.answering import GroundedAnswerSynthesizer
from apps.api.application.chunking import TextChunker
from apps.api.application.ontology import OntologyExtractor
from apps.api.application.ports import (
    AgentRunRepositoryPort,
    ApprovalRepositoryPort,
    AuditLogPort,
    DocumentRepositoryPort,
    EvaluationRepositoryPort,
    IdempotencyRepositoryPort,
    OntologyRepositoryPort,
    VectorSearchPort,
    WebhookDeliveryRepositoryPort,
    WebhookSubscriptionRepositoryPort,
)
from apps.api.application.query_classifier import QueryClassifier
from apps.api.application.retrieval_strategy import RetrievalPlanner
from apps.api.application.use_cases import (
    ApprovalUseCase,
    EvaluateAgentUseCase,
    IngestDocumentUseCase,
    OperationsAlertUseCase,
    OperationsSloUseCase,
    OperationsSummaryUseCase,
    OperationsUsageUseCase,
    RetentionPruneUseCase,
    RunAgentUseCase,
    SearchKnowledgeUseCase,
    ToolCallUseCase,
)
from apps.api.application.webhooks import WebhookDispatcher
from apps.api.core.config import get_settings
from apps.api.domain.policies import AgentPolicy, RedactionPolicy, ToolPolicy


class AppContainer:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.documents: DocumentRepositoryPort
        self.audit_log: AuditLogPort
        self.base_audit_log: AuditLogPort
        self.runs: AgentRunRepositoryPort
        self.approvals: ApprovalRepositoryPort
        self.evaluations: EvaluationRepositoryPort
        self.idempotency: IdempotencyRepositoryPort
        self.ontology: OntologyRepositoryPort
        self.webhook_subscriptions: WebhookSubscriptionRepositoryPort
        self.webhook_deliveries: WebhookDeliveryRepositoryPort
        self.webhook_dispatcher: WebhookDispatcher
        self.vector_search: VectorSearchPort

        if settings.storage_backend == "postgres":
            self.documents = PostgresDocumentRepository(settings.postgres_dsn)
            self.base_audit_log = PostgresAuditLog(settings.postgres_dsn)
            self.runs = PostgresAgentRunRepository(settings.postgres_dsn)
            self.approvals = PostgresApprovalRepository(settings.postgres_dsn)
            self.evaluations = PostgresEvaluationRepository(settings.postgres_dsn)
            self.idempotency = PostgresIdempotencyRepository(settings.postgres_dsn)
            self.ontology = PostgresOntologyRepository(settings.postgres_dsn)
            self.webhook_subscriptions = PostgresWebhookSubscriptionRepository(
                settings.postgres_dsn
            )
            self.webhook_deliveries = PostgresWebhookDeliveryRepository(settings.postgres_dsn)
        else:
            self.documents = InMemoryDocumentRepository()
            self.base_audit_log = InMemoryAuditLog()
            self.runs = InMemoryAgentRunRepository()
            self.approvals = InMemoryApprovalRepository()
            self.evaluations = InMemoryEvaluationRepository()
            self.idempotency = InMemoryIdempotencyRepository()
            self.ontology = InMemoryOntologyRepository()
            self.webhook_subscriptions = InMemoryWebhookSubscriptionRepository()
            self.webhook_deliveries = InMemoryWebhookDeliveryRepository()

        self.audit_log = RequestContextAuditLog(
            inner=OutboxAuditLog(
                inner=self.base_audit_log,
                subscriptions=self.webhook_subscriptions,
                deliveries=self.webhook_deliveries,
            )
        )
        self.webhook_http_client = UrllibWebhookHttpClient()
        self.webhook_dispatcher = WebhookDispatcher(
            subscriptions=self.webhook_subscriptions,
            deliveries=self.webhook_deliveries,
            http_client=self.webhook_http_client,
            timeout_seconds=settings.webhook_timeout_seconds,
            max_attempts=settings.webhook_max_attempts,
            lease_seconds=settings.webhook_lease_seconds,
        )

        if settings.vector_backend == "qdrant":
            self.vector_search = QdrantVectorSearch(
                url=settings.qdrant_url,
                collection_name=settings.qdrant_collection,
                dimensions=settings.embedding_dimensions,
            )
        else:
            self.vector_search = LocalKeywordVectorSearch()

        self.chunker = TextChunker()
        self.ontology_extractor = OntologyExtractor()
        self.classifier = QueryClassifier()
        self.planner = RetrievalPlanner()
        self.redaction_policy = RedactionPolicy()
        self.agent_policy = AgentPolicy()
        self.tool_policy = ToolPolicy()
        self.tool_registry = LocalToolRegistry()
        self.tool_gateway = ResilientToolGateway(inner=LocalToolGateway())
        self.tool_runtime = LocalToolRuntime(
            policy=self.tool_policy,
            registry=self.tool_registry,
            gateway=self.tool_gateway,
        )
        self.synthesizer = GroundedAnswerSynthesizer()

        self.ingest_document = IngestDocumentUseCase(
            documents=self.documents,
            vector_search=self.vector_search,
            audit_log=self.audit_log,
            chunker=self.chunker,
            ontology=self.ontology,
            ontology_extractor=self.ontology_extractor,
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
            monthly_agent_run_quota=settings.monthly_agent_run_quota,
        )
        self.call_tool = ToolCallUseCase(
            registry=self.tool_registry,
            tool_runtime=self.tool_runtime,
            runs=self.runs,
            approvals=self.approvals,
            audit_log=self.audit_log,
        )
        self.approval = ApprovalUseCase(
            approvals=self.approvals,
            tool_runtime=self.tool_runtime,
            audit_log=self.audit_log,
        )
        self.evaluate_agent = EvaluateAgentUseCase(
            evaluations=self.evaluations,
            run_agent=self.run_agent,
            audit_log=self.audit_log,
        )
        self.operations_summary = OperationsSummaryUseCase(
            documents=self.documents,
            approvals=self.approvals,
            audit_log=self.audit_log,
        )
        self.operations_usage = OperationsUsageUseCase(
            runs=self.runs,
            monthly_agent_run_quota=settings.monthly_agent_run_quota,
        )
        self.operations_slo = OperationsSloUseCase(
            audit_log=self.audit_log,
        )
        self.operations_alerts = OperationsAlertUseCase(
            operations_summary=self.operations_summary,
            operations_usage=self.operations_usage,
        )
        self.retention_prune = RetentionPruneUseCase(
            audit_log=self.audit_log,
            webhook_deliveries=self.webhook_deliveries,
        )


@lru_cache(maxsize=1)
def get_container() -> AppContainer:
    return AppContainer()
