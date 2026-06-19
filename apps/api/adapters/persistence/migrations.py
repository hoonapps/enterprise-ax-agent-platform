from __future__ import annotations

import psycopg
from psycopg.rows import dict_row

from apps.api.domain.models import SchemaMigrationRecord


class PostgresMigrationLedger:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def list_applied(self) -> tuple[bool, list[SchemaMigrationRecord]]:
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            exists = conn.execute(
                "select to_regclass('public.schema_migrations') is not null as exists"
            ).fetchone()
            if not exists or not exists["exists"]:
                return False, []

            rows = conn.execute(
                """
                select version, filename, checksum, applied_at
                from schema_migrations
                order by version
                """
            ).fetchall()
            return True, [
                SchemaMigrationRecord(
                    version=str(row["version"]),
                    filename=str(row["filename"]),
                    checksum=str(row["checksum"]),
                    applied_at=row["applied_at"],
                )
                for row in rows
            ]
