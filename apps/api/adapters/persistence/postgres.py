from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, cast
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from apps.api.domain.models import (
    AgentRun,
    AgentScenarioRunResult,
    AgentScenarioStepResult,
    ApprovalRequest,
    ApprovalStatus,
    AuditEvent,
    Citation,
    Classification,
    Document,
    DocumentChunk,
    EvaluationCase,
    EvaluationRun,
    EvaluationStatus,
    IdempotencyRecord,
    OntologyEdge,
    OntologyGraph,
    OntologyNode,
    PolicyDecision,
    QueryType,
    RunStatus,
    ToolActionType,
    ToolDecision,
    ToolExecution,
    TraceStep,
    WebhookDelivery,
    WebhookDeliveryStatus,
    WebhookSubscription,
)


class PostgresBase:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def _set_tenant_context(self, conn: Any, tenant_pk: UUID) -> None:
        conn.execute("select set_config('app.tenant_id', %s, true)", (str(tenant_pk),))

    def _tenant_pk(self, tenant_slug: str) -> UUID:
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            row = conn.execute(
                """
                insert into tenants (slug, name)
                values (%s, %s)
                on conflict (slug) do update set name = excluded.name
                returning id
                """,
                (tenant_slug, tenant_slug),
            ).fetchone()
            if row is None:
                raise RuntimeError("tenant upsert failed")
            return cast(UUID, row["id"])


class PostgresDocumentRepository(PostgresBase):
    def save_document(self, document: Document, chunks: list[DocumentChunk]) -> Document:
        tenant_pk = self._tenant_pk(document.tenant_id)
        content_hash = hashlib.sha256(document.content.encode("utf-8")).hexdigest()

        with psycopg.connect(self.dsn) as conn:
            self._set_tenant_context(conn, tenant_pk)
            conn.execute(
                """
                insert into documents (
                  id, tenant_id, source_type, source_uri, title,
                  content_hash, classification, metadata, created_at
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (tenant_id, content_hash) do nothing
                """,
                (
                    document.id,
                    tenant_pk,
                    document.source_type,
                    document.source_uri,
                    document.title,
                    content_hash,
                    document.classification.value,
                    Jsonb(document.metadata),
                    document.created_at,
                ),
            )
            for chunk in chunks:
                conn.execute(
                    """
                    insert into document_chunks (
                      id, tenant_id, document_id, chunk_index, content,
                      token_count, metadata, embedding_ref, created_at
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s, now())
                    on conflict (tenant_id, document_id, chunk_index)
                    do update set
                      content = excluded.content,
                      token_count = excluded.token_count,
                      metadata = excluded.metadata,
                      embedding_ref = excluded.embedding_ref
                    """,
                    (
                        chunk.id,
                        tenant_pk,
                        chunk.document_id,
                        chunk.chunk_index,
                        chunk.content,
                        len(chunk.content.split()),
                        Jsonb(chunk.metadata),
                        chunk.embedding_ref,
                    ),
                )

        return document

    def list_documents(self, tenant_id: str) -> list[Document]:
        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            self._set_tenant_context(conn, tenant_pk)
            rows = conn.execute(
                """
                select d.id, t.slug as tenant_id, d.title, d.source_type,
                       d.source_uri, d.classification, d.metadata, d.created_at
                from documents d
                join tenants t on t.id = d.tenant_id
                where t.slug = %s
                order by d.created_at desc
                """,
                (tenant_id,),
            ).fetchall()

        return [
            Document(
                id=cast(UUID, row["id"]),
                tenant_id=cast(str, row["tenant_id"]),
                title=cast(str, row["title"]),
                content="",
                source_type=cast(str, row["source_type"]),
                source_uri=cast(str, row["source_uri"]),
                classification=Classification(cast(str, row["classification"])),
                metadata=cast(dict[str, Any], row["metadata"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]


class PostgresOntologyRepository(PostgresBase):
    def upsert(self, nodes: list[OntologyNode], edges: list[OntologyEdge]) -> None:
        if not nodes and not edges:
            return
        tenant_id = (nodes[0].tenant_id if nodes else edges[0].tenant_id)
        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn) as conn:
            self._set_tenant_context(conn, tenant_pk)
            for node in nodes:
                conn.execute(
                    """
                    insert into ontology_nodes (
                      tenant_id, node_key, label, node_type, source_document_id,
                      evidence_count, metadata, created_at, updated_at
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (tenant_id, node_key) do update set
                      evidence_count = ontology_nodes.evidence_count + excluded.evidence_count,
                      metadata = ontology_nodes.metadata || excluded.metadata,
                      updated_at = excluded.updated_at
                    """,
                    (
                        tenant_pk,
                        node.node_key,
                        node.label,
                        node.node_type,
                        node.source_document_id,
                        node.evidence_count,
                        Jsonb(node.metadata),
                        node.created_at,
                        node.updated_at,
                    ),
                )
            for edge in edges:
                conn.execute(
                    """
                    insert into ontology_edges (
                      tenant_id, source_key, target_key, relation,
                      evidence_count, metadata, created_at, updated_at
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (tenant_id, source_key, target_key, relation) do update set
                      evidence_count = ontology_edges.evidence_count + excluded.evidence_count,
                      metadata = ontology_edges.metadata || excluded.metadata,
                      updated_at = excluded.updated_at
                    """,
                    (
                        tenant_pk,
                        edge.source_key,
                        edge.target_key,
                        edge.relation,
                        edge.evidence_count,
                        Jsonb(edge.metadata),
                        edge.created_at,
                        edge.updated_at,
                    ),
                )

    def get_graph(self, tenant_id: str, limit: int = 200) -> OntologyGraph:
        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            self._set_tenant_context(conn, tenant_pk)
            node_rows = conn.execute(
                """
                select n.*, t.slug as tenant_slug
                from ontology_nodes n
                join tenants t on t.id = n.tenant_id
                where t.slug = %s
                order by n.evidence_count desc, n.node_key asc
                limit %s
                """,
                (tenant_id, limit),
            ).fetchall()
            node_keys = [row["node_key"] for row in node_rows]
            if node_keys:
                edge_rows = conn.execute(
                    """
                    select e.*, t.slug as tenant_slug
                    from ontology_edges e
                    join tenants t on t.id = e.tenant_id
                    where t.slug = %s
                      and e.source_key = any(%s)
                      and e.target_key = any(%s)
                    order by e.evidence_count desc, e.source_key asc, e.target_key asc
                    limit %s
                    """,
                    (tenant_id, node_keys, node_keys, limit),
                ).fetchall()
            else:
                edge_rows = []
        return OntologyGraph(
            tenant_id=tenant_id,
            nodes=[self._row_to_node(row) for row in node_rows],
            edges=[self._row_to_edge(row) for row in edge_rows],
        )

    def _row_to_node(self, row: dict[str, Any]) -> OntologyNode:
        return OntologyNode(
            tenant_id=cast(str, row["tenant_slug"]),
            node_key=cast(str, row["node_key"]),
            label=cast(str, row["label"]),
            node_type=cast(str, row["node_type"]),
            source_document_id=cast(UUID | None, row["source_document_id"]),
            evidence_count=int(row["evidence_count"]),
            metadata=cast(dict[str, Any], row["metadata"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_edge(self, row: dict[str, Any]) -> OntologyEdge:
        return OntologyEdge(
            tenant_id=cast(str, row["tenant_slug"]),
            source_key=cast(str, row["source_key"]),
            target_key=cast(str, row["target_key"]),
            relation=cast(str, row["relation"]),
            evidence_count=int(row["evidence_count"]),
            metadata=cast(dict[str, Any], row["metadata"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class PostgresAgentRunRepository(PostgresBase):
    def save(self, run: AgentRun) -> AgentRun:
        tenant_pk = self._tenant_pk(run.tenant_id)
        metadata = {
            "citations": [
                {
                    "document_id": str(citation.document_id),
                    "chunk_id": str(citation.chunk_id),
                    "title": citation.title,
                    "score": citation.score,
                    "source_uri": citation.source_uri,
                }
                for citation in run.citations
            ],
            "trace": [step.__dict__ for step in run.trace],
            "policy": run.policy_decision.__dict__,
            "tool_executions": [
                {
                    "id": str(execution.id),
                    "tool_name": execution.tool_name,
                    "action_type": execution.action_type.value,
                    "decision": execution.decision.value,
                    "status": execution.status,
                    "reason": execution.reason,
                    "input_payload": execution.input_payload,
                    "output_payload": execution.output_payload,
                }
                for execution in run.tool_executions
            ],
        }

        with psycopg.connect(self.dsn) as conn:
            self._set_tenant_context(conn, tenant_pk)
            conn.execute(
                """
                insert into agent_runs (
                  id, tenant_id, scenario, query, redacted_query, query_type,
                  status, confidence, created_at, completed_at
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (id) do update set
                  status = excluded.status,
                  confidence = excluded.confidence,
                  completed_at = excluded.completed_at
                """,
                (
                    run.id,
                    tenant_pk,
                    run.scenario,
                    run.query,
                    run.redacted_query,
                    run.query_type.value,
                    run.status.value,
                    run.confidence,
                    run.created_at,
                    run.completed_at,
                ),
            )
            conn.execute(
                """
                insert into agent_messages (
                  tenant_id, agent_run_id, role, content, metadata
                )
                values (%s, %s, %s, %s, %s)
                """,
                (tenant_pk, run.id, "assistant", run.answer, Jsonb(metadata)),
            )
            for execution in run.tool_executions:
                conn.execute(
                    """
                    insert into tool_calls (
                      id, tenant_id, agent_run_id, tool_name, action_type,
                      input_payload, output_payload, policy_decision, status,
                      latency_ms, created_at
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    on conflict (id) do nothing
                    """,
                    (
                        execution.id,
                        tenant_pk,
                        run.id,
                        execution.tool_name,
                        execution.action_type.value,
                        Jsonb(execution.input_payload),
                        Jsonb(execution.output_payload),
                        execution.decision.value,
                        execution.status,
                        None,
                    ),
                )

        return run

    def get(self, tenant_id: str, run_id: str) -> AgentRun | None:
        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            self._set_tenant_context(conn, tenant_pk)
            row = conn.execute(
                """
                select r.*, t.slug as tenant_slug, m.content as answer, m.metadata
                from agent_runs r
                join tenants t on t.id = r.tenant_id
                left join lateral (
                  select content, metadata
                  from agent_messages
                  where agent_run_id = r.id and role = 'assistant'
                  order by created_at desc
                  limit 1
                ) m on true
                where t.slug = %s and r.id = %s
                """,
                (tenant_id, UUID(run_id)),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_run(row)

    def list_runs(
        self,
        tenant_id: str,
        limit: int = 50,
        scenario: str | None = None,
        status: str | None = None,
        query_type: str | None = None,
    ) -> list[AgentRun]:
        filters = ["t.slug = %s"]
        params: list[Any] = [tenant_id]
        if scenario is not None:
            filters.append("r.scenario = %s")
            params.append(scenario)
        if status is not None:
            filters.append("r.status = %s")
            params.append(status)
        if query_type is not None:
            filters.append("r.query_type = %s")
            params.append(query_type)
        params.append(limit)

        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            self._set_tenant_context(conn, tenant_pk)
            rows = conn.execute(
                f"""
                select r.*, t.slug as tenant_slug, m.content as answer, m.metadata
                from agent_runs r
                join tenants t on t.id = r.tenant_id
                left join lateral (
                  select content, metadata
                  from agent_messages
                  where agent_run_id = r.id and role = 'assistant'
                  order by created_at desc
                  limit 1
                ) m on true
                where {" and ".join(filters)}
                order by r.created_at desc
                limit %s
                """,
                params,
            ).fetchall()

        return [self._row_to_run(row) for row in rows]

    def count_runs_between(self, tenant_id: str, start: datetime, end: datetime) -> int:
        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn) as conn:
            self._set_tenant_context(conn, tenant_pk)
            row = conn.execute(
                """
                select count(*)
                from agent_runs r
                join tenants t on t.id = r.tenant_id
                where t.slug = %s
                  and r.created_at >= %s
                  and r.created_at < %s
                """,
                (tenant_id, start, end),
            ).fetchone()
        return int(row[0]) if row else 0

    def _row_to_run(self, row: dict[str, Any]) -> AgentRun:
        metadata = cast(dict[str, Any], row["metadata"] or {})
        return AgentRun(
            id=cast(UUID, row["id"]),
            tenant_id=cast(str, row["tenant_slug"]),
            scenario=cast(str, row["scenario"]),
            query=cast(str, row["query"]),
            redacted_query=cast(str, row["redacted_query"]),
            query_type=QueryType(cast(str, row["query_type"])),
            answer=cast(str, row["answer"] or ""),
            status=RunStatus(cast(str, row["status"])),
            citations=self._citations(metadata.get("citations", [])),
            trace=self._trace(metadata.get("trace", [])),
            confidence=float(row["confidence"]),
            policy_decision=self._policy(metadata.get("policy", {})),
            tool_executions=self._tool_executions(metadata.get("tool_executions", [])),
            user_id=None,
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )

    def _citations(self, raw: Any) -> list[Citation]:
        if not isinstance(raw, list):
            return []
        citations: list[Citation] = []
        for item in raw:
            if isinstance(item, dict):
                citations.append(
                    Citation(
                        document_id=UUID(str(item["document_id"])),
                        chunk_id=UUID(str(item["chunk_id"])),
                        title=str(item["title"]),
                        score=float(item["score"]),
                        source_uri=str(item["source_uri"]),
                    )
                )
        return citations

    def _trace(self, raw: Any) -> list[TraceStep]:
        if not isinstance(raw, list):
            return []
        return [
            TraceStep(
                step=str(item.get("step", "unknown")),
                status=str(item.get("status", "unknown")),
                detail=cast(dict[str, Any], item.get("detail", {})),
            )
            for item in raw
            if isinstance(item, dict)
        ]

    def _policy(self, raw: Any) -> PolicyDecision:
        if not isinstance(raw, dict):
            return PolicyDecision(
                allowed=True,
                decision="unknown",
                reason="No policy metadata was stored.",
            )
        return PolicyDecision(
            allowed=bool(raw.get("allowed", True)),
            decision=str(raw.get("decision", "unknown")),
            reason=str(raw.get("reason", "")),
            redactions=int(raw.get("redactions", 0)),
        )

    def _tool_executions(self, raw: Any) -> list[ToolExecution]:
        if not isinstance(raw, list):
            return []

        executions: list[ToolExecution] = []
        for item in raw:
            if isinstance(item, dict):
                executions.append(
                    ToolExecution(
                        id=UUID(str(item["id"])),
                        tool_name=str(item["tool_name"]),
                        action_type=ToolActionType(str(item["action_type"])),
                        decision=ToolDecision(str(item["decision"])),
                        status=str(item["status"]),
                        reason=str(item["reason"]),
                        input_payload=cast(dict[str, Any], item.get("input_payload", {})),
                        output_payload=cast(dict[str, Any], item.get("output_payload", {})),
                    )
                )
        return executions


class PostgresAgentScenarioRunRepository(PostgresBase):
    def save(self, result: AgentScenarioRunResult) -> AgentScenarioRunResult:
        tenant_pk = self._tenant_pk(result.tenant_id)
        with psycopg.connect(self.dsn) as conn:
            self._set_tenant_context(conn, tenant_pk)
            conn.execute(
                """
                insert into agent_scenario_runs (
                  id, tenant_id, scenario_id, name, status, metrics,
                  step_results, created_at
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (id) do update set
                  status = excluded.status,
                  metrics = excluded.metrics,
                  step_results = excluded.step_results
                """,
                (
                    result.id,
                    tenant_pk,
                    result.scenario_id,
                    result.name,
                    result.status,
                    Jsonb(result.metrics),
                    Jsonb([self._step_to_dict(step) for step in result.step_results]),
                    result.generated_at,
                ),
            )
        return result

    def list_runs(
        self,
        tenant_id: str,
        limit: int = 20,
        scenario_id: str | None = None,
        status: str | None = None,
    ) -> list[AgentScenarioRunResult]:
        filters = ["t.slug = %s"]
        params: list[Any] = [tenant_id]
        if scenario_id is not None:
            filters.append("r.scenario_id = %s")
            params.append(scenario_id)
        if status is not None:
            filters.append("r.status = %s")
            params.append(status)
        params.append(limit)

        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            self._set_tenant_context(conn, tenant_pk)
            rows = conn.execute(
                f"""
                select r.*, t.slug as tenant_slug
                from agent_scenario_runs r
                join tenants t on t.id = r.tenant_id
                where {" and ".join(filters)}
                order by r.created_at desc
                limit %s
                """,
                params,
            ).fetchall()
        return [self._row_to_result(row) for row in rows]

    def _step_to_dict(self, step: AgentScenarioStepResult) -> dict[str, Any]:
        return {
            "step_id": step.step_id,
            "title": step.title,
            "run_id": str(step.run_id),
            "status": step.status,
            "query_type": step.query_type,
            "confidence": step.confidence,
            "citation_count": step.citation_count,
            "tool_decision_counts": step.tool_decision_counts,
            "passed": step.passed,
            "failed_checks": step.failed_checks,
        }

    def _row_to_result(self, row: dict[str, Any]) -> AgentScenarioRunResult:
        return AgentScenarioRunResult(
            id=cast(UUID, row["id"]),
            tenant_id=cast(str, row["tenant_slug"]),
            scenario_id=cast(str, row["scenario_id"]),
            name=cast(str, row["name"]),
            status=cast(str, row["status"]),
            step_results=[
                self._step_from_dict(item)
                for item in cast(list[Any], row["step_results"])
                if isinstance(item, dict)
            ],
            metrics=cast(dict[str, Any], row["metrics"]),
            generated_at=row["created_at"],
        )

    def _step_from_dict(self, item: dict[str, Any]) -> AgentScenarioStepResult:
        return AgentScenarioStepResult(
            step_id=str(item["step_id"]),
            title=str(item["title"]),
            run_id=UUID(str(item["run_id"])),
            status=str(item["status"]),
            query_type=str(item["query_type"]),
            confidence=float(item["confidence"]),
            citation_count=int(item["citation_count"]),
            tool_decision_counts={
                str(key): int(value)
                for key, value in cast(dict[str, Any], item["tool_decision_counts"]).items()
            },
            passed=bool(item["passed"]),
            failed_checks=[str(value) for value in cast(list[Any], item["failed_checks"])],
        )


class PostgresAuditLog(PostgresBase):
    def append(self, event: AuditEvent) -> None:
        tenant_pk = self._tenant_pk(event.tenant_id)
        with psycopg.connect(self.dsn) as conn:
            self._set_tenant_context(conn, tenant_pk)
            conn.execute(
                """
                insert into audit_events (
                  id, tenant_id, actor_type, actor_id, event_type,
                  resource_type, resource_id, payload, created_at
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    event.id,
                    tenant_pk,
                    event.actor_type,
                    event.actor_id,
                    event.event_type,
                    event.resource_type,
                    event.resource_id,
                    Jsonb(event.payload),
                    event.created_at,
                ),
            )

    def list_events(
        self,
        tenant_id: str,
        limit: int,
        event_type: str | None = None,
        resource_type: str | None = None,
        request_id: str | None = None,
    ) -> list[AuditEvent]:
        filters = ["t.slug = %s"]
        params: list[Any] = [tenant_id]
        if event_type is not None:
            filters.append("e.event_type = %s")
            params.append(event_type)
        if resource_type is not None:
            filters.append("e.resource_type = %s")
            params.append(resource_type)
        if request_id is not None:
            filters.append("e.payload ->> 'request_id' = %s")
            params.append(request_id)
        params.append(limit)

        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            self._set_tenant_context(conn, tenant_pk)
            rows = conn.execute(
                f"""
                select e.*, t.slug as tenant_slug
                from audit_events e
                join tenants t on t.id = e.tenant_id
                where {" and ".join(filters)}
                order by e.created_at desc
                limit %s
                """,
                params,
            ).fetchall()

        return [
            AuditEvent(
                id=cast(UUID, row["id"]),
                tenant_id=cast(str, row["tenant_slug"]),
                actor_type=cast(str, row["actor_type"]),
                actor_id=cast(str, row["actor_id"]),
                event_type=cast(str, row["event_type"]),
                resource_type=cast(str, row["resource_type"]),
                resource_id=cast(UUID | None, row["resource_id"]),
                payload=cast(dict[str, Any], row["payload"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def count_events_before(self, tenant_id: str, before: datetime) -> int:
        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn) as conn:
            self._set_tenant_context(conn, tenant_pk)
            row = conn.execute(
                """
                select count(*)
                from audit_events e
                join tenants t on t.id = e.tenant_id
                where t.slug = %s
                  and e.created_at < %s
                  and not exists (
                    select 1
                    from webhook_deliveries d
                    where d.event_id = e.id
                      and d.status in (%s, %s, %s)
                  )
                """,
                (
                    tenant_id,
                    before,
                    WebhookDeliveryStatus.PENDING.value,
                    WebhookDeliveryStatus.DISPATCHING.value,
                    WebhookDeliveryStatus.FAILED.value,
                ),
            ).fetchone()
        return int(row[0]) if row else 0

    def delete_events_before(self, tenant_id: str, before: datetime) -> int:
        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn) as conn:
            self._set_tenant_context(conn, tenant_pk)
            cursor = conn.execute(
                """
                delete from audit_events e
                using tenants t
                where t.id = e.tenant_id
                  and t.slug = %s
                  and e.created_at < %s
                  and not exists (
                    select 1
                    from webhook_deliveries d
                    where d.event_id = e.id
                      and d.status in (%s, %s, %s)
                  )
                """,
                (
                    tenant_id,
                    before,
                    WebhookDeliveryStatus.PENDING.value,
                    WebhookDeliveryStatus.DISPATCHING.value,
                    WebhookDeliveryStatus.FAILED.value,
                ),
            )
        return cursor.rowcount if cursor.rowcount is not None else 0


class PostgresWebhookSubscriptionRepository(PostgresBase):
    def save(self, subscription: WebhookSubscription) -> WebhookSubscription:
        tenant_pk = self._tenant_pk(subscription.tenant_id)
        with psycopg.connect(self.dsn) as conn:
            self._set_tenant_context(conn, tenant_pk)
            conn.execute(
                """
                insert into webhook_subscriptions (
                  id, tenant_id, name, target_url, event_types,
                  secret, enabled, created_at
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (id) do update set
                  name = excluded.name,
                  target_url = excluded.target_url,
                  event_types = excluded.event_types,
                  secret = excluded.secret,
                  enabled = excluded.enabled
                """,
                (
                    subscription.id,
                    tenant_pk,
                    subscription.name,
                    subscription.target_url,
                    subscription.event_types,
                    subscription.secret,
                    subscription.enabled,
                    subscription.created_at,
                ),
            )
        return subscription

    def get(self, tenant_id: str, subscription_id: str) -> WebhookSubscription | None:
        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            self._set_tenant_context(conn, tenant_pk)
            row = conn.execute(
                """
                select s.*, t.slug as tenant_slug
                from webhook_subscriptions s
                join tenants t on t.id = s.tenant_id
                where t.slug = %s and s.id = %s
                """,
                (tenant_id, UUID(subscription_id)),
            ).fetchone()
        return self._row_to_subscription(row) if row else None

    def list_subscriptions(self, tenant_id: str) -> list[WebhookSubscription]:
        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            self._set_tenant_context(conn, tenant_pk)
            rows = conn.execute(
                """
                select s.*, t.slug as tenant_slug
                from webhook_subscriptions s
                join tenants t on t.id = s.tenant_id
                where t.slug = %s
                order by s.created_at desc
                """,
                (tenant_id,),
            ).fetchall()
        return [self._row_to_subscription(row) for row in rows]

    def list_enabled_for_event(
        self,
        tenant_id: str,
        event_type: str,
    ) -> list[WebhookSubscription]:
        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            self._set_tenant_context(conn, tenant_pk)
            rows = conn.execute(
                """
                select s.*, t.slug as tenant_slug
                from webhook_subscriptions s
                join tenants t on t.id = s.tenant_id
                where t.slug = %s
                  and s.enabled = true
                  and (%s = any(s.event_types) or '*' = any(s.event_types))
                order by s.created_at desc
                """,
                (tenant_id, event_type),
            ).fetchall()
        return [self._row_to_subscription(row) for row in rows]

    def _row_to_subscription(self, row: dict[str, Any]) -> WebhookSubscription:
        return WebhookSubscription(
            id=cast(UUID, row["id"]),
            tenant_id=cast(str, row["tenant_slug"]),
            name=cast(str, row["name"]),
            target_url=cast(str, row["target_url"]),
            event_types=[str(item) for item in cast(list[Any], row["event_types"])],
            secret=cast(str | None, row["secret"]),
            enabled=bool(row["enabled"]),
            created_at=row["created_at"],
        )


class PostgresWebhookDeliveryRepository(PostgresBase):
    def save(self, delivery: WebhookDelivery) -> WebhookDelivery:
        tenant_pk = self._tenant_pk(delivery.tenant_id)
        with psycopg.connect(self.dsn) as conn:
            self._set_tenant_context(conn, tenant_pk)
            conn.execute(
                """
                insert into webhook_deliveries (
                  id, tenant_id, subscription_id, event_id, event_type, target_url,
                  payload, status, attempt_count, next_attempt_at, last_error,
                  created_at, delivered_at
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (id) do update set
                  status = excluded.status,
                  attempt_count = excluded.attempt_count,
                  next_attempt_at = excluded.next_attempt_at,
                  last_error = excluded.last_error,
                  delivered_at = excluded.delivered_at
                """,
                (
                    delivery.id,
                    tenant_pk,
                    delivery.subscription_id,
                    delivery.event_id,
                    delivery.event_type,
                    delivery.target_url,
                    Jsonb(delivery.payload),
                    delivery.status.value,
                    delivery.attempt_count,
                    delivery.next_attempt_at,
                    delivery.last_error,
                    delivery.created_at,
                    delivery.delivered_at,
                ),
            )
        return delivery

    def list_deliveries(
        self,
        tenant_id: str,
        status: WebhookDeliveryStatus | None = None,
        limit: int = 100,
    ) -> list[WebhookDelivery]:
        filters = ["t.slug = %s"]
        params: list[Any] = [tenant_id]
        if status is not None:
            filters.append("d.status = %s")
            params.append(status.value)
        params.append(limit)
        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            self._set_tenant_context(conn, tenant_pk)
            rows = conn.execute(
                f"""
                select d.*, t.slug as tenant_slug
                from webhook_deliveries d
                join tenants t on t.id = d.tenant_id
                where {" and ".join(filters)}
                order by d.created_at desc
                limit %s
                """,
                params,
            ).fetchall()
        return [self._row_to_delivery(row) for row in rows]

    def list_dispatchable(
        self,
        tenant_id: str,
        now: datetime,
        limit: int = 100,
    ) -> list[WebhookDelivery]:
        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            self._set_tenant_context(conn, tenant_pk)
            rows = conn.execute(
                """
                select d.*, t.slug as tenant_slug
                from webhook_deliveries d
                join tenants t on t.id = d.tenant_id
                where t.slug = %s
                  and (
                    d.status = %s
                    or (
                      d.status in (%s, %s)
                      and (d.next_attempt_at is null or d.next_attempt_at <= %s)
                    )
                  )
                order by coalesce(d.next_attempt_at, d.created_at) asc, d.created_at asc
                limit %s
                """,
                (
                    tenant_id,
                    WebhookDeliveryStatus.PENDING.value,
                    WebhookDeliveryStatus.FAILED.value,
                    WebhookDeliveryStatus.DISPATCHING.value,
                    now,
                    limit,
                ),
            ).fetchall()
        return [self._row_to_delivery(row) for row in rows]

    def claim_dispatchable(
        self,
        tenant_id: str,
        now: datetime,
        lease_until: datetime,
        limit: int = 100,
    ) -> list[WebhookDelivery]:
        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            self._set_tenant_context(conn, tenant_pk)
            rows = conn.execute(
                """
                with candidates as (
                  select d.id
                  from webhook_deliveries d
                  join tenants t on t.id = d.tenant_id
                  where t.slug = %s
                    and (
                      d.status = %s
                      or (
                        d.status in (%s, %s)
                        and (d.next_attempt_at is null or d.next_attempt_at <= %s)
                      )
                    )
                  order by coalesce(d.next_attempt_at, d.created_at) asc, d.created_at asc
                  limit %s
                  for update skip locked
                ),
                updated as (
                  update webhook_deliveries d
                  set status = %s,
                      next_attempt_at = %s
                  from candidates c
                  where d.id = c.id
                  returning d.*
                )
                select u.*, t.slug as tenant_slug
                from updated u
                join tenants t on t.id = u.tenant_id
                order by coalesce(u.next_attempt_at, u.created_at) asc, u.created_at asc
                """,
                (
                    tenant_id,
                    WebhookDeliveryStatus.PENDING.value,
                    WebhookDeliveryStatus.FAILED.value,
                    WebhookDeliveryStatus.DISPATCHING.value,
                    now,
                    limit,
                    WebhookDeliveryStatus.DISPATCHING.value,
                    lease_until,
                ),
            ).fetchall()
        return [self._row_to_delivery(row) for row in rows]

    def get(self, tenant_id: str, delivery_id: str) -> WebhookDelivery | None:
        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            self._set_tenant_context(conn, tenant_pk)
            row = conn.execute(
                """
                select d.*, t.slug as tenant_slug
                from webhook_deliveries d
                join tenants t on t.id = d.tenant_id
                where t.slug = %s and d.id = %s
                """,
                (tenant_id, UUID(delivery_id)),
            ).fetchone()
        return self._row_to_delivery(row) if row else None

    def count_terminal_before(self, tenant_id: str, before: datetime) -> int:
        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn) as conn:
            self._set_tenant_context(conn, tenant_pk)
            row = conn.execute(
                """
                select count(*)
                from webhook_deliveries d
                join tenants t on t.id = d.tenant_id
                where t.slug = %s
                  and d.created_at < %s
                  and d.status in (%s, %s)
                """,
                (
                    tenant_id,
                    before,
                    WebhookDeliveryStatus.DELIVERED.value,
                    WebhookDeliveryStatus.DEAD_LETTER.value,
                ),
            ).fetchone()
        return int(row[0]) if row else 0

    def delete_terminal_before(self, tenant_id: str, before: datetime) -> int:
        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn) as conn:
            self._set_tenant_context(conn, tenant_pk)
            cursor = conn.execute(
                """
                delete from webhook_deliveries d
                using tenants t
                where t.id = d.tenant_id
                  and t.slug = %s
                  and d.created_at < %s
                  and d.status in (%s, %s)
                """,
                (
                    tenant_id,
                    before,
                    WebhookDeliveryStatus.DELIVERED.value,
                    WebhookDeliveryStatus.DEAD_LETTER.value,
                ),
            )
        return cursor.rowcount if cursor.rowcount is not None else 0

    def _row_to_delivery(self, row: dict[str, Any]) -> WebhookDelivery:
        return WebhookDelivery(
            id=cast(UUID, row["id"]),
            tenant_id=cast(str, row["tenant_slug"]),
            subscription_id=cast(UUID, row["subscription_id"]),
            event_id=cast(UUID, row["event_id"]),
            event_type=cast(str, row["event_type"]),
            target_url=cast(str, row["target_url"]),
            payload=cast(dict[str, Any], row["payload"]),
            status=WebhookDeliveryStatus(cast(str, row["status"])),
            attempt_count=int(row["attempt_count"]),
            next_attempt_at=row["next_attempt_at"],
            last_error=cast(str | None, row["last_error"]),
            created_at=row["created_at"],
            delivered_at=row["delivered_at"],
        )


class PostgresApprovalRepository(PostgresBase):
    def save(self, approval: ApprovalRequest) -> ApprovalRequest:
        tenant_pk = self._tenant_pk(approval.tenant_id)
        with psycopg.connect(self.dsn) as conn:
            self._set_tenant_context(conn, tenant_pk)
            conn.execute(
                """
                insert into approval_requests (
                  id, tenant_id, agent_run_id, tool_execution_id, tool_name,
                  action_type, input_payload, reason, status, requested_by,
                  approved_by, replay_result, created_at, updated_at
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (id) do update set
                  status = excluded.status,
                  approved_by = excluded.approved_by,
                  replay_result = excluded.replay_result,
                  updated_at = excluded.updated_at
                """,
                (
                    approval.id,
                    tenant_pk,
                    approval.agent_run_id,
                    approval.tool_execution_id,
                    approval.tool_name,
                    approval.action_type.value,
                    Jsonb(approval.input_payload),
                    approval.reason,
                    approval.status.value,
                    approval.requested_by,
                    approval.approved_by,
                    Jsonb(approval.replay_result),
                    approval.created_at,
                    approval.updated_at,
                ),
            )
        return approval

    def list_pending(self, tenant_id: str) -> list[ApprovalRequest]:
        return self._list(tenant_id=tenant_id, status=ApprovalStatus.PENDING)

    def get(self, tenant_id: str, approval_id: str) -> ApprovalRequest | None:
        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            self._set_tenant_context(conn, tenant_pk)
            row = conn.execute(
                """
                select a.*, t.slug as tenant_slug
                from approval_requests a
                join tenants t on t.id = a.tenant_id
                where t.slug = %s and a.id = %s
                """,
                (tenant_id, UUID(approval_id)),
            ).fetchone()
        return self._row_to_approval(row) if row else None

    def _list(self, *, tenant_id: str, status: ApprovalStatus) -> list[ApprovalRequest]:
        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            self._set_tenant_context(conn, tenant_pk)
            rows = conn.execute(
                """
                select a.*, t.slug as tenant_slug
                from approval_requests a
                join tenants t on t.id = a.tenant_id
                where t.slug = %s and a.status = %s
                order by a.created_at desc
                """,
                (tenant_id, status.value),
            ).fetchall()
        return [self._row_to_approval(row) for row in rows]

    def _row_to_approval(self, row: dict[str, Any]) -> ApprovalRequest:
        return ApprovalRequest(
            id=cast(UUID, row["id"]),
            tenant_id=cast(str, row["tenant_slug"]),
            agent_run_id=cast(UUID, row["agent_run_id"]),
            tool_execution_id=cast(UUID, row["tool_execution_id"]),
            tool_name=cast(str, row["tool_name"]),
            action_type=ToolActionType(cast(str, row["action_type"])),
            input_payload=cast(dict[str, Any], row["input_payload"]),
            reason=cast(str, row["reason"]),
            status=ApprovalStatus(cast(str, row["status"])),
            requested_by=cast(str | None, row["requested_by"]),
            approved_by=cast(str | None, row["approved_by"]),
            replay_result=cast(dict[str, Any], row["replay_result"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class PostgresEvaluationRepository(PostgresBase):
    def save(self, run: EvaluationRun, cases: list[EvaluationCase]) -> EvaluationRun:
        tenant_pk = self._tenant_pk(run.tenant_id)
        with psycopg.connect(self.dsn) as conn:
            self._set_tenant_context(conn, tenant_pk)
            conn.execute(
                """
                insert into evaluation_runs (
                  id, tenant_id, name, scenario, status, metrics, created_at, completed_at
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (id) do update set
                  status = excluded.status,
                  metrics = excluded.metrics,
                  completed_at = excluded.completed_at
                """,
                (
                    run.id,
                    tenant_pk,
                    run.name,
                    run.scenario,
                    run.status.value,
                    Jsonb(run.metrics),
                    run.created_at,
                    run.completed_at,
                ),
            )
            for case in cases:
                conn.execute(
                    """
                    insert into evaluation_cases (
                      id, tenant_id, evaluation_run_id, input_query, expected_facts,
                      actual_answer, score, failure_reason, created_at
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (id) do update set
                      actual_answer = excluded.actual_answer,
                      score = excluded.score,
                      failure_reason = excluded.failure_reason
                    """,
                    (
                        case.id,
                        tenant_pk,
                        run.id,
                        case.input_query,
                        Jsonb(case.expected_facts),
                        case.actual_answer,
                        case.score,
                        case.failure_reason,
                        case.created_at,
                    ),
                )
        return EvaluationRun(
            id=run.id,
            tenant_id=run.tenant_id,
            name=run.name,
            scenario=run.scenario,
            status=run.status,
            metrics=run.metrics,
            cases=cases,
            created_at=run.created_at,
            completed_at=run.completed_at,
        )

    def get(self, tenant_id: str, evaluation_run_id: str) -> EvaluationRun | None:
        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            self._set_tenant_context(conn, tenant_pk)
            run_row = conn.execute(
                """
                select r.*, t.slug as tenant_slug
                from evaluation_runs r
                join tenants t on t.id = r.tenant_id
                where t.slug = %s and r.id = %s
                """,
                (tenant_id, UUID(evaluation_run_id)),
            ).fetchone()
            if run_row is None:
                return None

            case_rows = conn.execute(
                """
                select c.*, t.slug as tenant_slug
                from evaluation_cases c
                join tenants t on t.id = c.tenant_id
                where t.slug = %s and c.evaluation_run_id = %s
                order by c.created_at asc
                """,
                (tenant_id, UUID(evaluation_run_id)),
            ).fetchall()

        cases = [
            EvaluationCase(
                id=cast(UUID, row["id"]),
                tenant_id=cast(str, row["tenant_slug"]),
                evaluation_run_id=cast(UUID, row["evaluation_run_id"]),
                input_query=cast(str, row["input_query"]),
                expected_facts=[str(item) for item in cast(list[Any], row["expected_facts"])],
                actual_answer=cast(str, row["actual_answer"] or ""),
                score=float(row["score"] or 0.0),
                failure_reason=cast(str | None, row["failure_reason"]),
                created_at=row["created_at"],
            )
            for row in case_rows
        ]
        return EvaluationRun(
            id=cast(UUID, run_row["id"]),
            tenant_id=cast(str, run_row["tenant_slug"]),
            name=cast(str, run_row["name"]),
            scenario=cast(str, run_row["scenario"]),
            status=EvaluationStatus(cast(str, run_row["status"])),
            metrics=cast(dict[str, Any], run_row["metrics"]),
            cases=cases,
            created_at=run_row["created_at"],
            completed_at=run_row["completed_at"],
        )


class PostgresIdempotencyRepository(PostgresBase):
    def get(self, tenant_id: str, key: str) -> IdempotencyRecord | None:
        tenant_pk = self._tenant_pk(tenant_id)
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            self._set_tenant_context(conn, tenant_pk)
            row = conn.execute(
                """
                select i.*, t.slug as tenant_slug
                from idempotency_keys i
                join tenants t on t.id = i.tenant_id
                where t.slug = %s and i.key = %s
                """,
                (tenant_id, key),
            ).fetchone()
        if row is None:
            return None
        return IdempotencyRecord(
            tenant_id=cast(str, row["tenant_slug"]),
            key=cast(str, row["key"]),
            request_hash=cast(str, row["request_hash"]),
            response_payload=cast(dict[str, Any], row["response_payload"] or {}),
            created_at=row["created_at"],
        )

    def save(self, record: IdempotencyRecord) -> IdempotencyRecord:
        tenant_pk = self._tenant_pk(record.tenant_id)
        with psycopg.connect(self.dsn) as conn:
            self._set_tenant_context(conn, tenant_pk)
            conn.execute(
                """
                insert into idempotency_keys (
                  tenant_id, key, request_hash, response_payload, created_at
                )
                values (%s, %s, %s, %s, %s)
                on conflict (tenant_id, key) do update set
                  response_payload = excluded.response_payload
                """,
                (
                    tenant_pk,
                    record.key,
                    record.request_hash,
                    Jsonb(record.response_payload),
                    record.created_at,
                ),
            )
        return record
