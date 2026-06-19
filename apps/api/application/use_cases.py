from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any
from uuid import UUID

from apps.api.application.answering import GroundedAnswerSynthesizer
from apps.api.application.chunking import TextChunker
from apps.api.application.ontology import OntologyExtractor
from apps.api.application.ports import (
    AgentRunRepositoryPort,
    ApprovalRepositoryPort,
    AuditLogPort,
    DocumentRepositoryPort,
    EvaluationRepositoryPort,
    OntologyRepositoryPort,
    ToolRegistryPort,
    ToolRuntimePort,
    VectorSearchPort,
    WebhookDeliveryRepositoryPort,
)
from apps.api.application.query_classifier import QueryClassifier
from apps.api.application.retrieval_strategy import RetrievalPlanner
from apps.api.domain.models import (
    AgentRun,
    ApprovalRequest,
    ApprovalStatus,
    AuditEvent,
    Document,
    EvaluationCase,
    EvaluationRun,
    EvaluationStatus,
    OperationsSummary,
    PolicyDecision,
    QueryType,
    RetentionPruneResult,
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
        ontology: OntologyRepositoryPort,
        ontology_extractor: OntologyExtractor,
    ) -> None:
        self.documents = documents
        self.vector_search = vector_search
        self.audit_log = audit_log
        self.chunker = chunker
        self.ontology = ontology
        self.ontology_extractor = ontology_extractor

    def execute(self, document: Document, actor_id: str = "system") -> tuple[Document, int]:
        chunks = self.chunker.split(document)
        saved = self.documents.save_document(document, chunks)
        self.vector_search.upsert(chunks)
        extracted = self.ontology_extractor.extract(saved)
        self.ontology.upsert(extracted.nodes, extracted.edges)
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
                    "ontology_node_count": len(extracted.nodes),
                    "ontology_edge_count": len(extracted.edges),
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


class ToolCallUseCase:
    def __init__(
        self,
        *,
        registry: ToolRegistryPort,
        tool_runtime: ToolRuntimePort,
        runs: AgentRunRepositoryPort,
        approvals: ApprovalRepositoryPort,
        audit_log: AuditLogPort,
    ) -> None:
        self.registry = registry
        self.tool_runtime = tool_runtime
        self.runs = runs
        self.approvals = approvals
        self.audit_log = audit_log

    def execute(
        self,
        *,
        tenant_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        actor_id: str,
        actor_scopes: list[str],
    ) -> ToolExecution:
        definition = self.registry.get(tool_name)
        if definition is None:
            execution = ToolExecution(
                tool_name=tool_name,
                action_type=ToolActionType.READ,
                decision=ToolDecision.DENIED,
                status="skipped",
                reason="등록되지 않은 tool 요청입니다.",
                input_payload=arguments,
            )
            run = self._record_run(tenant_id=tenant_id, actor_id=actor_id, execution=execution)
            self._audit_execution(
                tenant_id=tenant_id,
                actor_id=actor_id,
                run=run,
                execution=execution,
            )
            return execution

        missing = self._missing_required_arguments(definition.input_schema, arguments)
        if missing:
            execution = ToolExecution(
                tool_name=tool_name,
                action_type=definition.action_type,
                decision=ToolDecision.DENIED,
                status="skipped",
                reason=f"필수 입력이 없습니다: {', '.join(missing)}",
                input_payload=arguments,
            )
        else:
            execution = self.tool_runtime.execute(
                ToolRequest(
                    name=definition.name,
                    action_type=definition.action_type,
                    input_payload=arguments,
                    actor_scopes=actor_scopes,
                    risk_level=definition.risk_level,
                    description=definition.description,
                )
            )

        run = self._record_run(tenant_id=tenant_id, actor_id=actor_id, execution=execution)
        self._audit_execution(tenant_id=tenant_id, actor_id=actor_id, run=run, execution=execution)
        if execution.decision == ToolDecision.APPROVAL_REQUIRED:
            self._create_approval_request(
                tenant_id=tenant_id,
                actor_id=actor_id,
                run=run,
                execution=execution,
            )
        return execution

    def _record_run(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        execution: ToolExecution,
    ) -> AgentRun:
        now = datetime.now(UTC)
        run = AgentRun(
            tenant_id=tenant_id,
            user_id=actor_id,
            scenario="mcp-tool-call",
            query=f"tool:{execution.tool_name}",
            redacted_query=f"tool:{execution.tool_name}",
            query_type=QueryType.ACTION,
            answer=execution.reason,
            status=RunStatus.BLOCKED
            if execution.decision == ToolDecision.DENIED
            else RunStatus.SUCCEEDED,
            citations=[],
            trace=[
                TraceStep(
                    step="mcp_tool_call",
                    status=execution.status,
                    detail={
                        "tool_name": execution.tool_name,
                        "action_type": execution.action_type.value,
                        "decision": execution.decision.value,
                    },
                )
            ],
            confidence=1.0 if execution.decision == ToolDecision.ALLOWED else 0.0,
            policy_decision=PolicyDecision(
                allowed=execution.decision != ToolDecision.DENIED,
                decision=execution.decision.value,
                reason=execution.reason,
            ),
            tool_executions=[execution],
            completed_at=now,
        )
        return self.runs.save(run)

    def _audit_execution(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        run: AgentRun,
        execution: ToolExecution,
    ) -> None:
        self.audit_log.append(
            AuditEvent(
                tenant_id=tenant_id,
                actor_type="mcp_client",
                actor_id=actor_id,
                event_type=f"tool.{execution.decision.value}",
                resource_type="tool_call",
                resource_id=execution.id,
                payload={
                    "agent_run_id": str(run.id),
                    "tool_name": execution.tool_name,
                    "action_type": execution.action_type.value,
                    "status": execution.status,
                    "reason": execution.reason,
                    "input_payload": execution.input_payload,
                    "output_payload": execution.output_payload,
                },
            )
        )

    def _create_approval_request(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        run: AgentRun,
        execution: ToolExecution,
    ) -> None:
        approval = ApprovalRequest(
            id=execution.id,
            tenant_id=tenant_id,
            agent_run_id=run.id,
            tool_execution_id=execution.id,
            tool_name=execution.tool_name,
            action_type=execution.action_type,
            input_payload=execution.input_payload,
            reason=execution.reason,
            requested_by=actor_id,
        )
        self.approvals.save(approval)
        self.audit_log.append(
            AuditEvent(
                tenant_id=tenant_id,
                actor_type="mcp_client",
                actor_id=actor_id,
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

    def _missing_required_arguments(
        self,
        input_schema: dict[str, Any],
        arguments: dict[str, Any],
    ) -> list[str]:
        required = input_schema.get("required", [])
        if not isinstance(required, list):
            return []
        return [field for field in required if isinstance(field, str) and field not in arguments]


class EvaluateAgentUseCase:
    def __init__(
        self,
        *,
        evaluations: EvaluationRepositoryPort,
        run_agent: RunAgentUseCase,
        audit_log: AuditLogPort,
        pass_threshold: float = 0.7,
    ) -> None:
        self.evaluations = evaluations
        self.run_agent = run_agent
        self.audit_log = audit_log
        self.pass_threshold = pass_threshold

    def execute(
        self,
        *,
        tenant_id: str,
        name: str,
        scenario: str,
        cases: list[EvaluationCase],
        actor_id: str = "evaluation",
    ) -> EvaluationRun:
        started = datetime.now(UTC)
        evaluated_cases: list[EvaluationCase] = []

        run = EvaluationRun(
            tenant_id=tenant_id,
            name=name,
            scenario=scenario,
            status=EvaluationStatus.RUNNING,
            created_at=started,
        )

        for case in cases:
            agent_run = self.run_agent.execute(
                tenant_id=tenant_id,
                scenario=scenario,
                message=case.input_query,
                user_id=actor_id,
                actor_scopes=[],
            )
            score, failure_reason = self._score(
                answer=agent_run.answer,
                expected_facts=case.expected_facts,
            )
            evaluated_cases.append(
                EvaluationCase(
                    id=case.id,
                    tenant_id=tenant_id,
                    evaluation_run_id=run.id,
                    input_query=case.input_query,
                    expected_facts=case.expected_facts,
                    actual_answer=agent_run.answer,
                    score=score,
                    failure_reason=failure_reason,
                    created_at=case.created_at,
                )
            )

        metrics = self._metrics(evaluated_cases)
        completed = EvaluationRun(
            id=run.id,
            tenant_id=tenant_id,
            name=name,
            scenario=scenario,
            status=EvaluationStatus.COMPLETED,
            metrics=metrics,
            cases=evaluated_cases,
            created_at=started,
            completed_at=datetime.now(UTC),
        )
        saved = self.evaluations.save(completed, evaluated_cases)
        self.audit_log.append(
            AuditEvent(
                tenant_id=tenant_id,
                actor_type="system",
                actor_id=actor_id,
                event_type="evaluation.completed",
                resource_type="evaluation_run",
                resource_id=saved.id,
                payload={
                    "name": saved.name,
                    "scenario": saved.scenario,
                    "metrics": saved.metrics,
                    "case_count": len(saved.cases),
                },
            )
        )
        return saved

    def get(self, *, tenant_id: str, evaluation_run_id: UUID) -> EvaluationRun | None:
        return self.evaluations.get(tenant_id=tenant_id, evaluation_run_id=str(evaluation_run_id))

    def _score(self, *, answer: str, expected_facts: list[str]) -> tuple[float, str | None]:
        if not expected_facts:
            return (1.0, None) if answer.strip() else (0.0, "답변이 비어 있습니다.")

        normalized_answer = self._normalize(answer)
        matched = [
            fact
            for fact in expected_facts
            if self._normalize(fact) and self._normalize(fact) in normalized_answer
        ]
        score = round(len(matched) / len(expected_facts), 3)
        if score >= self.pass_threshold:
            return score, None
        missing = [fact for fact in expected_facts if fact not in matched]
        return score, "누락된 기대 사실: " + ", ".join(missing)

    def _metrics(self, cases: list[EvaluationCase]) -> dict[str, float | int]:
        case_count = len(cases)
        if case_count == 0:
            return {
                "case_count": 0,
                "average_score": 0.0,
                "pass_rate": 0.0,
                "failed_count": 0,
            }

        passed = [case for case in cases if case.score >= self.pass_threshold]
        average_score = round(sum(case.score for case in cases) / case_count, 3)
        pass_rate = round(len(passed) / case_count, 3)
        return {
            "case_count": case_count,
            "average_score": average_score,
            "pass_rate": pass_rate,
            "failed_count": case_count - len(passed),
        }

    def _normalize(self, value: str) -> str:
        return " ".join(value.casefold().split())


class OperationsSummaryUseCase:
    def __init__(
        self,
        *,
        documents: DocumentRepositoryPort,
        approvals: ApprovalRepositoryPort,
        audit_log: AuditLogPort,
    ) -> None:
        self.documents = documents
        self.approvals = approvals
        self.audit_log = audit_log

    def execute(self, *, tenant_id: str, event_limit: int = 500) -> OperationsSummary:
        events = self.audit_log.list_events(tenant_id=tenant_id, limit=event_limit)
        agent_events = [event for event in events if event.event_type == "agent.answer.generated"]
        latencies = [
            int(event.payload["latency_ms"])
            for event in agent_events
            if isinstance(event.payload.get("latency_ms"), int)
        ]
        confidences = [
            float(event.payload["confidence"])
            for event in agent_events
            if isinstance(event.payload.get("confidence"), int | float)
        ]

        return OperationsSummary(
            tenant_id=tenant_id,
            event_limit=event_limit,
            document_count=len(self.documents.list_documents(tenant_id)),
            pending_approval_count=len(self.approvals.list_pending(tenant_id)),
            agent_run_count=len(agent_events),
            average_latency_ms=self._average(latencies),
            average_confidence=self._average(confidences),
            event_counts=self._event_counts(events),
            tool_decision_counts=self._tool_decision_counts(events),
            approval_counts=self._approval_counts(events),
            gateway_fallback_count=self._gateway_fallback_count(events),
            latest_evaluation_metrics=self._latest_evaluation_metrics(events),
        )

    def _event_counts(self, events: list[AuditEvent]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for event in events:
            counts[event.event_type] = counts.get(event.event_type, 0) + 1
        return counts

    def _tool_decision_counts(self, events: list[AuditEvent]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for event in events:
            if not event.event_type.startswith("tool."):
                continue
            decision = event.event_type.removeprefix("tool.")
            counts[decision] = counts.get(decision, 0) + 1
        return counts

    def _approval_counts(self, events: list[AuditEvent]) -> dict[str, int]:
        counts = {"requested": 0, "executed": 0, "rejected": 0}
        for event in events:
            if event.event_type == "approval.requested":
                counts["requested"] += 1
            elif event.event_type == "approval.executed":
                counts["executed"] += 1
            elif event.event_type == "approval.rejected":
                counts["rejected"] += 1
        return counts

    def _gateway_fallback_count(self, events: list[AuditEvent]) -> int:
        count = 0
        for event in events:
            output_payload = event.payload.get("output_payload")
            if not isinstance(output_payload, dict):
                continue
            gateway = output_payload.get("_gateway")
            if isinstance(gateway, dict) and gateway.get("fallback_used") is True:
                count += 1
        return count

    def _latest_evaluation_metrics(self, events: list[AuditEvent]) -> dict[str, Any]:
        for event in events:
            if event.event_type != "evaluation.completed":
                continue
            metrics = event.payload.get("metrics")
            return metrics if isinstance(metrics, dict) else {}
        return {}

    def _average(self, values: list[int] | list[float]) -> float:
        if not values:
            return 0.0
        return round(sum(values) / len(values), 3)


class RetentionPruneUseCase:
    def __init__(
        self,
        *,
        audit_log: AuditLogPort,
        webhook_deliveries: WebhookDeliveryRepositoryPort,
    ) -> None:
        self.audit_log = audit_log
        self.webhook_deliveries = webhook_deliveries

    def execute(
        self,
        *,
        tenant_id: str,
        audit_older_than_days: int,
        webhook_older_than_days: int,
        dry_run: bool,
        actor_id: str,
        now: datetime | None = None,
    ) -> RetentionPruneResult:
        reference_time = now or datetime.now(UTC)
        audit_cutoff = reference_time - timedelta(days=audit_older_than_days)
        webhook_cutoff = reference_time - timedelta(days=webhook_older_than_days)

        audit_count = self.audit_log.count_events_before(tenant_id, audit_cutoff)
        webhook_count = self.webhook_deliveries.count_terminal_before(tenant_id, webhook_cutoff)

        audit_deleted = 0
        webhook_deleted = 0
        if not dry_run:
            webhook_deleted = self.webhook_deliveries.delete_terminal_before(
                tenant_id,
                webhook_cutoff,
            )
            audit_deleted = self.audit_log.delete_events_before(tenant_id, audit_cutoff)

        result = RetentionPruneResult(
            tenant_id=tenant_id,
            dry_run=dry_run,
            audit_cutoff=audit_cutoff,
            webhook_cutoff=webhook_cutoff,
            audit_events_matched=audit_count,
            webhook_deliveries_matched=webhook_count,
            audit_events_deleted=audit_deleted,
            webhook_deliveries_deleted=webhook_deleted,
        )
        self.audit_log.append(
            AuditEvent(
                tenant_id=tenant_id,
                actor_type="operator",
                actor_id=actor_id,
                event_type="retention.pruned",
                resource_type="operations",
                payload={
                    "dry_run": dry_run,
                    "audit_cutoff": audit_cutoff.isoformat(),
                    "webhook_cutoff": webhook_cutoff.isoformat(),
                    "audit_events_matched": audit_count,
                    "webhook_deliveries_matched": webhook_count,
                    "audit_events_deleted": audit_deleted,
                    "webhook_deliveries_deleted": webhook_deleted,
                },
            )
        )
        return result


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

    def reject(
        self,
        *,
        tenant_id: str,
        approval_id: UUID,
        rejected_by: str,
        reason: str,
    ) -> ApprovalRequest | None:
        approval = self.approvals.get(tenant_id=tenant_id, approval_id=str(approval_id))
        if approval is None:
            return None

        if approval.status != ApprovalStatus.PENDING:
            return approval

        updated = replace(
            approval,
            status=ApprovalStatus.REJECTED,
            approved_by=rejected_by,
            replay_result={
                "decision": "rejected",
                "rejected_by": rejected_by,
                "reason": reason,
            },
            updated_at=datetime.now(UTC),
        )
        saved = self.approvals.save(updated)
        self.audit_log.append(
            AuditEvent(
                tenant_id=tenant_id,
                actor_type="user",
                actor_id=rejected_by,
                event_type="approval.rejected",
                resource_type="approval_request",
                resource_id=saved.id,
                payload={
                    "agent_run_id": str(saved.agent_run_id),
                    "tool_execution_id": str(saved.tool_execution_id),
                    "tool_name": saved.tool_name,
                    "reason": reason,
                },
            )
        )
        return saved
