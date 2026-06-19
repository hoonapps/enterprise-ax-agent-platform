from __future__ import annotations

import os
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def main() -> None:
    dsn = os.getenv(
        "POSTGRES_DSN",
        "postgresql://ax_agent_app:ax_agent_app@localhost:5432/ax_agent",
    )
    alpha_slug = "rls-alpha"
    beta_slug = "rls-beta"
    event_type = "rls.smoke"
    alpha_resource_id = uuid4()
    beta_resource_id = uuid4()

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        alpha_tenant_id = _upsert_tenant(conn, alpha_slug)
        beta_tenant_id = _upsert_tenant(conn, beta_slug)

        _set_tenant(conn, alpha_tenant_id)
        _insert_event(
            conn,
            tenant_id=alpha_tenant_id,
            actor_id="alpha-operator",
            event_type=event_type,
            resource_id=alpha_resource_id,
        )

        _set_tenant(conn, beta_tenant_id)
        _insert_event(
            conn,
            tenant_id=beta_tenant_id,
            actor_id="beta-operator",
            event_type=event_type,
            resource_id=beta_resource_id,
        )

        _assert_visible_count(
            conn,
            tenant_id=alpha_tenant_id,
            event_type=event_type,
            expected_count=1,
            expected_actor="alpha-operator",
        )
        _assert_visible_count(
            conn,
            tenant_id=beta_tenant_id,
            event_type=event_type,
            expected_count=1,
            expected_actor="beta-operator",
        )
        _assert_without_tenant_context(conn, event_type=event_type)

        _delete_events(conn, tenant_id=alpha_tenant_id, event_type=event_type)
        _delete_events(conn, tenant_id=beta_tenant_id, event_type=event_type)

    print("tenant RLS smoke test passed")


def _upsert_tenant(conn: Any, slug: str) -> UUID:
    row = conn.execute(
        """
        insert into tenants (slug, name)
        values (%s, %s)
        on conflict (slug) do update set name = excluded.name
        returning id
        """,
        (slug, slug),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"tenant upsert failed: {slug}")
    return UUID(str(row["id"]))


def _set_tenant(conn: Any, tenant_id: UUID | None) -> None:
    conn.execute(
        "select set_config('app.tenant_id', %s, true)",
        (str(tenant_id) if tenant_id else "",),
    )


def _insert_event(
    conn: Any,
    *,
    tenant_id: UUID,
    actor_id: str,
    event_type: str,
    resource_id: UUID,
) -> None:
    conn.execute(
        """
        insert into audit_events (
          id, tenant_id, actor_type, actor_id, event_type, resource_type,
          resource_id, payload, created_at
        )
        values (%s, %s, 'system', %s, %s, 'rls_check', %s, %s, now())
        """,
        (
            uuid4(),
            tenant_id,
            actor_id,
            event_type,
            resource_id,
            Jsonb({"source": "verify_tenant_rls"}),
        ),
    )


def _assert_visible_count(
    conn: Any,
    *,
    tenant_id: UUID,
    event_type: str,
    expected_count: int,
    expected_actor: str,
) -> None:
    _set_tenant(conn, tenant_id)
    rows = conn.execute(
        """
        select actor_id
        from audit_events
        where event_type = %s
        order by actor_id
        """,
        (event_type,),
    ).fetchall()
    actors = [str(row["actor_id"]) for row in rows]
    if len(actors) != expected_count or actors != [expected_actor]:
        raise RuntimeError(
            f"tenant context {tenant_id} saw {actors}; expected {[expected_actor]}"
        )


def _assert_without_tenant_context(conn: Any, *, event_type: str) -> None:
    _set_tenant(conn, None)
    row = conn.execute(
        "select count(*) as count from audit_events where event_type = %s",
        (event_type,),
    ).fetchone()
    count = int(row["count"]) if row else 0
    if count != 0:
        raise RuntimeError(f"query without tenant context saw {count} events; expected 0")


def _delete_events(
    conn: Any,
    *,
    tenant_id: UUID,
    event_type: str,
) -> None:
    _set_tenant(conn, tenant_id)
    conn.execute("delete from audit_events where event_type = %s", (event_type,))


if __name__ == "__main__":
    main()
