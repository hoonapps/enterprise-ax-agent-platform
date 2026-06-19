from __future__ import annotations

import hashlib
from typing import Any, cast
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from apps.api.domain.models import (
    AgentRun,
    AuditEvent,
    Citation,
    Classification,
    Document,
    DocumentChunk,
    PolicyDecision,
    QueryType,
    RunStatus,
    TraceStep,
)


class PostgresBase:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

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
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
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
        }

        with psycopg.connect(self.dsn) as conn:
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

        return run

    def get(self, tenant_id: str, run_id: str) -> AgentRun | None:
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
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


class PostgresAuditLog(PostgresBase):
    def append(self, event: AuditEvent) -> None:
        tenant_pk = self._tenant_pk(event.tenant_id)
        with psycopg.connect(self.dsn) as conn:
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

    def list_events(self, tenant_id: str, limit: int) -> list[AuditEvent]:
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            rows = conn.execute(
                """
                select e.*, t.slug as tenant_slug
                from audit_events e
                join tenants t on t.id = e.tenant_id
                where t.slug = %s
                order by e.created_at desc
                limit %s
                """,
                (tenant_id, limit),
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
