from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID

from apps.api.application.answering import GroundedAnswerSynthesizer
from apps.api.application.chunking import TextChunker
from apps.api.application.ports import (
    AgentRunRepositoryPort,
    ApprovalRepositoryPort,
    AuditLogPort,
    DocumentRepositoryPort,
    ToolRuntimePort,
    VectorSearchPort,
)
from apps.api.application.query_classifier import QueryClassifier
from apps.api.application.retrieval_strategy import RetrievalPlanner
from apps.api.domain.models import (
    AgentRun,
    ApprovalRequest,
    ApprovalStatus,
    AuditEvent,
    Document,
    QueryType,
    RetrievalResult,
    RunStatus,
    ToolActionType,
    ToolDecision,
    ToolExecution,
    ToolRequest,
    TraceStep,
)
from apps.api.domain.policies import AgentPolicy, RedactionPolicy


class IngestDocumentUseCase:
    def __init__(
        self,
        *,
        documents: DocumentRepositoryPort,
        vector_search: VectorSearchPort,
        audit_log: AuditLogPort,
        chunker: TextChunker,
    ) -> None:
        self.documents = documents
        self.vector_search = vector_search
        self.audit_log = audit_log
        self.chunker = chunker

    def execute(self, document: Document, actor_id: str = "system") -> tuple[Document, int]:
        chunks = self.chunker.split(document)
        saved = self.documents.save_document(document, chunks)
        self.vector_search.upsert(chunks)
        self.audit_log.append(
            AuditEvent(
                tenant_id=document.tenant_id,
                actor_type="system",
                actor_id=actor_id,
                event_type="document.ingested",
                resource_type="document",
                resource_id=saved.id,
                payload={
                    "title": saved.title,
                    "source_type": saved.source_type,
                    "chunk_count": len(chunks),
                    "classification": saved.classification.value,
                },
            )
        )
        return saved, len(chunks)


class SearchKnowledgeUseCase:
    def __init__(self, *, vector_search: VectorSearchPort, audit_log: AuditLogPort) -> None:
        self.vector_search = vector_search
        self.audit_log = audit_log

    def execute(self, *, tenant_id: str, query: str, top_k: int) -> list[RetrievalResult]:
        results = self.vector_search.search(tenant_id=tenant_id, query=query, top_k=top_k)
        self.audit_log.append(
            AuditEvent(
                tenant_id=tenant_id,
                actor_type="system",
                actor_id="search",
                event_type="retrieval.executed",
                resource_type="knowledge",
                payload={"query": query, "top_k": top_k, "result_count": len(results)},
            )
        )
        return results


class RunAgentUseCase:
    def __init__(
        self,
        *,
        vector_search: VectorSearchPort,
        audit_log: AuditLogPort,
        runs: AgentRunRepositoryPort,
        approvals: ApprovalRepositoryPort,
        classifier: QueryClassifier,
        planner: RetrievalPlanner,
        redaction_policy: RedactionPolicy,
        agent_policy: AgentPolicy,
        tool_runtime: ToolRuntimePort,
        synthesizer: GroundedAnswerSynthesizer,
        default_top_k: int,
    ) -> None:
        self.vector_search = vector_search
        self.audit_log = audit_log
        self.runs = runs
        self.approvals = approvals
        self.classifier = classifier
        self.planner = planner
        self.redaction_policy = redaction_policy
        self.agent_policy = agent_policy
        self.tool_runtime = tool_runtime
        self.synthesizer = synthesizer
        self.default_top_k = default_top_k

    def execute(
        self,
        *,
        tenant_id: str,
        scenario: str,
        message: str,
        user_id: str | None,
        actor_scopes: list[str] | None = None,
    ) -> AgentRun:
        started = perf_counter()
        trace: list[TraceStep] = []

        redacted, redactions = self.redaction_policy.redact(message)
        trace.append(
            TraceStep(
                step="redact_input",
                status="succeeded",
                detail={"redactions": redactions},
            )
        )

        query_type = self.classifier.classify(redacted)
        trace.append(
            TraceStep(
                step="classify_query",
                status="succeeded",
                detail={"query_type": query_type.value},
            )
        )

        plan = self.planner.plan(query_type, self.default_top_k)
        trace.append(
            TraceStep(
                step="plan_retrieval",
                status="succeeded",
                detail={"strategy": plan.strategy},
            )
        )

        decision = self.agent_policy.evaluate(
            query_type=query_type, message=redacted, redactions=redactions
        )
        trace.append(
            TraceStep(
                step="policy_pre_check",
                status="succeeded" if decision.allowed else "blocked",
                detail={"decision": decision.decision, "reason": decision.reason},
            )
        )

        if not decision.allowed:
            run = AgentRun(
                tenant_id=tenant_id,
                user_id=user_id,
                scenario=scenario,
                query=message,
                redacted_query=redacted,
                query_type=query_type,
                answer="요청한 작업은 승인 절차가 필요하여 실행하지 않았습니다.",
                status=RunStatus.BLOCKED,
                citations=[],
                trace=trace,
                confidence=0.0,
                policy_decision=decision,
                completed_at=datetime.now(UTC),
            )
            self.runs.save(run)
            self._audit_agent_run(run)
            return run

        results = self.vector_search.search(tenant_id=tenant_id, query=redacted, top_k=plan.top_k)
        trace.append(
            TraceStep(
                step="retrieve_context",
                status="succeeded",
                detail={"strategy": plan.strategy, "result_count": len(results)},
            )
        )

        tool_executions = self._execute_tools_if_needed(
            tenant_id=tenant_id,
            query_type=query_type,
            message=redacted,
            user_id=user_id,
            actor_scopes=actor_scopes or [],
            trace=trace,
        )

        answer = self.synthesizer.synthesize(
            message=redacted,
            query_type=query_type,
            results=results,
            tool_executions=tool_executions,
        )
        citations = [result.citation() for result in results]
        confidence = self._confidence(results)
        trace.append(TraceStep(step="generate_grounded_answer", status="succeeded"))

        elapsed_ms = int((perf_counter() - started) * 1000)
        run = AgentRun(
            tenant_id=tenant_id,
            user_id=user_id,
            scenario=scenario,
            query=message,
            redacted_query=redacted,
            query_type=query_type,
            answer=answer,
            status=RunStatus.SUCCEEDED,
            citations=citations,
            trace=trace,
            confidence=confidence,
            policy_decision=decision,
            tool_executions=tool_executions,
            completed_at=datetime.now(UTC),
        )
        self.runs.save(run)
        self._create_approval_requests(run)
        self._audit_agent_run(run, latency_ms=elapsed_ms)
        return run

    def get_run(self, tenant_id: str, run_id: UUID) -> AgentRun | None:
        return self.runs.get(tenant_id=tenant_id, run_id=str(run_id))

    def _confidence(self, results: list[RetrievalResult]) -> float:
        if not results:
            return 0.0
        top_score = max(result.score for result in results)
        coverage_bonus = min(len(results) * 0.08, 0.24)
        return round(min(0.95, top_score + coverage_bonus), 3)

    def _execute_tools_if_needed(
        self,
        *,
        tenant_id: str,
        query_type: QueryType,
        message: str,
        user_id: str | None,
        actor_scopes: list[str],
        trace: list[TraceStep],
    ) -> list[ToolExecution]:
        if query_type != QueryType.ACTION:
            trace.append(
                TraceStep(
                    step="tool_runtime",
                    status="skipped",
                    detail={"reason": "query_type_does_not_require_tool"},
                )
            )
            return []

        request = self._build_tool_request(message=message, actor_scopes=actor_scopes)
        execution = self.tool_runtime.execute(request)
        trace.append(
            TraceStep(
                step="tool_runtime",
                status=execution.status,
                detail={
                    "tool_name": execution.tool_name,
                    "action_type": execution.action_type.value,
                    "decision": execution.decision.value,
                    "reason": execution.reason,
                },
            )
        )
        self.audit_log.append(
            AuditEvent(
                tenant_id=tenant_id,
                actor_type="agent",
                actor_id=user_id or "system",
                event_type=f"tool.{execution.decision.value}",
                resource_type="tool_call",
                resource_id=execution.id,
                payload={
                    "tool_name": execution.tool_name,
                    "action_type": execution.action_type.value,
                    "status": execution.status,
                    "reason": execution.reason,
                    "input_payload": execution.input_payload,
                    "output_payload": execution.output_payload,
                },
            )
        )
        return [execution]

    def _create_approval_requests(self, run: AgentRun) -> None:
        for execution in run.tool_executions:
            if execution.decision != ToolDecision.APPROVAL_REQUIRED:
                continue

            approval = ApprovalRequest(
                id=execution.id,
                tenant_id=run.tenant_id,
                agent_run_id=run.id,
                tool_execution_id=execution.id,
                tool_name=execution.tool_name,
                action_type=execution.action_type,
                input_payload=execution.input_payload,
                reason=execution.reason,
                requested_by=run.user_id,
            )
            self.approvals.save(approval)
            self.audit_log.append(
                AuditEvent(
                    tenant_id=run.tenant_id,
                    actor_type="agent",
                    actor_id=run.user_id or "system",
                    event_type="approval.requested",
                    resource_type="approval_request",
                    resource_id=approval.id,
                    payload={
                        "agent_run_id": str(run.id),
                        "tool_execution_id": str(execution.id),
                        "tool_name": execution.tool_name,
                        "action_type": execution.action_type.value,
                        "reason": execution.reason,
                    },
                )
            )

    def _build_tool_request(self, *, message: str, actor_scopes: list[str]) -> ToolRequest:
        lowered = message.lower()
        if any(keyword in lowered for keyword in ("조회", "확인", "search", "find", "get")):
            return ToolRequest(
                name="internal-records.lookup",
                action_type=ToolActionType.READ,
                input_payload={"query": message},
                actor_scopes=actor_scopes,
                risk_level="low",
                description="내부 업무 레코드 조회",
            )

        return ToolRequest(
            name="workflow.request-change",
            action_type=ToolActionType.WRITE,
            input_payload={"request": message},
            actor_scopes=actor_scopes,
            risk_level="high",
            description="외부 상태 변경이 필요한 업무 요청",
        )

    def _audit_agent_run(self, run: AgentRun, latency_ms: int | None = None) -> None:
        self.audit_log.append(
            AuditEvent(
                tenant_id=run.tenant_id,
                actor_type="agent",
                actor_id=run.user_id or "system",
                event_type="agent.answer.generated",
                resource_type="agent_run",
                resource_id=run.id,
                payload={
                    "scenario": run.scenario,
                    "query_type": run.query_type.value,
                    "status": run.status.value,
                    "confidence": run.confidence,
                    "citations": len(run.citations),
                    "policy_decision": run.policy_decision.decision,
                    "tool_executions": [
                        {
                            "tool_name": execution.tool_name,
                            "action_type": execution.action_type.value,
                            "decision": execution.decision.value,
                            "status": execution.status,
                        }
                        for execution in run.tool_executions
                    ],
                    "latency_ms": latency_ms,
                },
            )
        )


class ApprovalUseCase:
    def __init__(
        self,
        *,
        approvals: ApprovalRepositoryPort,
        tool_runtime: ToolRuntimePort,
        audit_log: AuditLogPort,
    ) -> None:
        self.approvals = approvals
        self.tool_runtime = tool_runtime
        self.audit_log = audit_log

    def list_pending(self, *, tenant_id: str) -> list[ApprovalRequest]:
        return self.approvals.list_pending(tenant_id)

    def approve(
        self,
        *,
        tenant_id: str,
        approval_id: UUID,
        approved_by: str,
    ) -> ApprovalRequest | None:
        approval = self.approvals.get(tenant_id=tenant_id, approval_id=str(approval_id))
        if approval is None:
            return None

        if approval.status == ApprovalStatus.EXECUTED:
            return approval

        if approval.status != ApprovalStatus.PENDING:
            return approval

        replay = self.tool_runtime.replay_approved(approval)
        updated = replace(
            approval,
            status=ApprovalStatus.EXECUTED,
            approved_by=approved_by,
            replay_result={
                "tool_execution_id": str(replay.id),
                "tool_name": replay.tool_name,
                "decision": replay.decision.value,
                "status": replay.status,
                "output_payload": replay.output_payload,
            },
            updated_at=datetime.now(UTC),
        )
        saved = self.approvals.save(updated)
        self.audit_log.append(
            AuditEvent(
                tenant_id=tenant_id,
                actor_type="user",
                actor_id=approved_by,
                event_type="approval.executed",
                resource_type="approval_request",
                resource_id=saved.id,
                payload={
                    "agent_run_id": str(saved.agent_run_id),
                    "tool_execution_id": str(saved.tool_execution_id),
                    "tool_name": saved.tool_name,
                    "replay_result": saved.replay_result,
                },
            )
        )
        return saved
