from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from apps.api.application.migrations import discover_migration_files
from apps.api.domain.models import MigrationFile

DEFAULT_ADMIN_DSN = "postgresql://ax_agent:ax_agent@localhost:5432/ax_agent"


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Postgres schema migration ledger.")
    parser.add_argument("command", choices=["status", "baseline", "apply"])
    parser.add_argument(
        "--dsn",
        default=_default_dsn(),
        help="Postgres owner/admin DSN. Defaults to POSTGRES_ADMIN_DSN.",
    )
    parser.add_argument(
        "--migrations-dir",
        default="db/migrations",
        help="Directory containing ordered .sql migration files.",
    )
    args = parser.parse_args()

    migrations_dir = Path(args.migrations_dir)
    files = discover_migration_files(migrations_dir)
    with psycopg.connect(args.dsn, row_factory=dict_row) as conn:
        if args.command == "status":
            _print_json(_status(conn, files))
            return
        if args.command == "baseline":
            _ensure_ledger(conn)
            for file in files:
                _record_migration(conn, file.version, file.filename, file.checksum)
            _print_json(_status(conn, files))
            return
        if args.command == "apply":
            _ensure_ledger(conn)
            applied = _applied_versions(conn)
            for file in files:
                if file.version in applied:
                    continue
                sql = migrations_dir.joinpath(file.filename).read_text(encoding="utf-8")
                conn.execute(sql)
                _record_migration(conn, file.version, file.filename, file.checksum)
            _print_json(_status(conn, files))


def _default_dsn() -> str:
    return (
        os.getenv("POSTGRES_ADMIN_DSN")
        or os.getenv("POSTGRES_DSN")
        or os.getenv("CONTAINER_POSTGRES_DSN")
        or DEFAULT_ADMIN_DSN
    )


def _ensure_ledger(conn: Any) -> None:
    conn.execute(
        """
        create table if not exists schema_migrations (
          version text primary key,
          filename text not null,
          checksum text not null,
          applied_at timestamptz not null default now()
        )
        """
    )
    _grant_ledger_select_if_role_exists(conn)


def _record_migration(conn: Any, version: str, filename: str, checksum: str) -> None:
    conn.execute(
        """
        insert into schema_migrations (version, filename, checksum)
        values (%s, %s, %s)
        on conflict (version) do update
        set filename = excluded.filename,
            checksum = excluded.checksum,
            applied_at = schema_migrations.applied_at
        """,
        (version, filename, checksum),
    )
    _grant_ledger_select_if_role_exists(conn)


def _applied_versions(conn: Any) -> set[str]:
    rows = conn.execute("select version from schema_migrations").fetchall()
    return {str(row["version"]) for row in rows}


def _status(conn: Any, files: list[MigrationFile]) -> dict[str, object]:
    ledger_available = _ledger_available(conn)
    applied = _applied_records(conn) if ledger_available else {}
    migrations: list[dict[str, object]] = []
    for file in files:
        record = applied.get(file.version)
        if record is None:
            migrations.append(
                {
                    "version": file.version,
                    "filename": file.filename,
                    "checksum": file.checksum,
                    "applied_checksum": None,
                    "status": "pending" if ledger_available else "not_tracked",
                    "applied_at": None,
                }
            )
            continue
        migrations.append(
            {
                "version": file.version,
                "filename": file.filename,
                "checksum": file.checksum,
                "applied_checksum": record["checksum"],
                "status": "applied"
                if record["checksum"] == file.checksum
                else "checksum_mismatch",
                "applied_at": _isoformat(record["applied_at"]),
            }
        )

    statuses = {str(item["status"]) for item in migrations}
    if not ledger_available:
        overall = "untracked"
    elif "checksum_mismatch" in statuses:
        overall = "checksum_mismatch"
    elif "pending" in statuses:
        overall = "pending"
    else:
        overall = "up_to_date"
    return {
        "ledger_available": ledger_available,
        "status": overall,
        "migrations": migrations,
    }


def _ledger_available(conn: Any) -> bool:
    row = conn.execute(
        "select to_regclass('public.schema_migrations') is not null as exists"
    ).fetchone()
    return bool(row and row["exists"])


def _grant_ledger_select_if_role_exists(conn: Any) -> None:
    conn.execute(
        """
        do $$
        begin
          if exists (select 1 from pg_roles where rolname = 'ax_agent_app') then
            grant select on schema_migrations to ax_agent_app;
          end if;
        end;
        $$
        """
    )


def _applied_records(conn: Any) -> dict[str, dict[str, object]]:
    rows = conn.execute(
        "select version, filename, checksum, applied_at from schema_migrations"
    ).fetchall()
    return {str(row["version"]): dict(row) for row in rows}


def _isoformat(value: object) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
