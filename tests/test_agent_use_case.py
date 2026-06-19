from apps.api.adapters.agent.local_tool_registry import LocalToolRegistry
from apps.api.adapters.agent.local_tool_runtime import LocalToolRuntime
from apps.api.adapters.persistence.in_memory import (
    InMemoryAgentRunRepository,
    InMemoryApprovalRepository,
    InMemoryAuditLog,
    InMemoryDocumentRepository,
)
from apps.api.adapters.vector.local_keyword import LocalKeywordVectorSearch
from apps.api.application.answering import GroundedAnswerSynthesizer
from apps.api.application.chunking import TextChunker
from apps.api.application.query_classifier import QueryClassifier
from apps.api.application.retrieval_strategy import RetrievalPlanner
from apps.api.application.use_cases import IngestDocumentUseCase, RunAgentUseCase
from apps.api.domain.models import Document, RunStatus, ToolDecision
from apps.api.domain.policies import AgentPolicy, RedactionPolicy, ToolPolicy


def build_use_cases():
    documents = InMemoryDocumentRepository()
    vector = LocalKeywordVectorSearch()
    audit = InMemoryAuditLog()
    runs = InMemoryAgentRunRepository()
    approvals = InMemoryApprovalRepository()
    registry = LocalToolRegistry()
    ingest = IngestDocumentUseCase(
        documents=documents,
        vector_search=vector,
        audit_log=audit,
        chunker=TextChunker(max_chars=300, overlap=40),
    )
    agent = RunAgentUseCase(
        vector_search=vector,
        audit_log=audit,
        runs=runs,
        approvals=approvals,
        classifier=QueryClassifier(),
        planner=RetrievalPlanner(),
        redaction_policy=RedactionPolicy(),
        agent_policy=AgentPolicy(),
        tool_runtime=LocalToolRuntime(policy=ToolPolicy(), registry=registry),
        synthesizer=GroundedAnswerSynthesizer(),
        default_top_k=4,
    )
    return ingest, agent, audit, approvals


def test_agent_returns_grounded_answer_with_citations():
    ingest, agent, audit, _ = build_use_cases()
    ingest.execute(
        Document(
            tenant_id="default",
            title="AX 거버넌스",
            content="Agent 실행은 개인정보 마스킹, 권한 검사, 감사로그를 반드시 포함해야 한다.",
            source_uri="test://governance",
        )
    )

    run = agent.execute(
        tenant_id="default",
        scenario="operations",
        message="Agent 거버넌스 리스크를 정리해줘",
        user_id="tester",
    )

    assert run.status == RunStatus.SUCCEEDED
    assert run.citations
    assert "감사" in run.answer
    assert audit.list_events("default", limit=10)


def test_destructive_action_requires_approval():
    _, agent, _, _ = build_use_cases()

    run = agent.execute(
        tenant_id="default",
        scenario="finance",
        message="고객 계좌로 100만원 송금 실행해줘",
        user_id="tester",
    )

    assert run.status == RunStatus.BLOCKED
    assert run.policy_decision.decision == "approval_required"
    assert not run.citations


def test_action_query_records_tool_approval_decision():
    ingest, agent, audit, approvals = build_use_cases()
    ingest.execute(
        Document(
            tenant_id="default",
            title="업무 실행 정책",
            content="외부 상태를 변경하는 업무 실행은 승인 대기 상태로 전환하고 감사로그에 남긴다.",
            source_uri="test://tool-policy",
        )
    )

    run = agent.execute(
        tenant_id="default",
        scenario="operations",
        message="보고서 생성 요청을 처리해줘",
        user_id="tester",
        actor_scopes=["workflow:request"],
    )

    assert run.status == RunStatus.SUCCEEDED
    assert run.tool_executions
    assert run.tool_executions[0].decision == ToolDecision.APPROVAL_REQUIRED
    assert run.tool_executions[0].status == "pending_approval"

    events = audit.list_events("default", limit=20)
    assert any(event.event_type == "tool.approval_required" for event in events)
    assert approvals.list_pending("default")


def test_action_query_without_required_scope_is_denied():
    ingest, agent, audit, approvals = build_use_cases()
    ingest.execute(
        Document(
            tenant_id="default",
            title="업무 실행 정책",
            content="외부 상태를 변경하는 업무 실행은 필요한 scope가 있어야 한다.",
            source_uri="test://tool-scope",
        )
    )

    run = agent.execute(
        tenant_id="default",
        scenario="operations",
        message="보고서 생성 요청을 처리해줘",
        user_id="tester",
        actor_scopes=[],
    )

    assert run.tool_executions
    assert run.tool_executions[0].decision == ToolDecision.DENIED
    assert not approvals.list_pending("default")
    events = audit.list_events("default", limit=20)
    assert any(event.event_type == "tool.denied" for event in events)
