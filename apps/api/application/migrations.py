from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from apps.api.application.ports import MigrationLedgerPort
from apps.api.domain.models import MigrationFile, MigrationStatus, MigrationStatusItem


class MigrationStatusUseCase:
    def __init__(
        self,
        *,
        migrations_dir: Path,
        storage_backend: str,
        ledger: MigrationLedgerPort | None = None,
    ) -> None:
        self.migrations_dir = migrations_dir
        self.storage_backend = storage_backend
        self.ledger = ledger

    def execute(self) -> MigrationStatus:
        files = discover_migration_files(self.migrations_dir)
        if self.storage_backend != "postgres" or self.ledger is None:
            return MigrationStatus(
                storage_backend=self.storage_backend,
                ledger_available=False,
                status="not_applicable",
                migrations=[
                    MigrationStatusItem(
                        version=file.version,
                        filename=file.filename,
                        checksum=file.checksum,
                        applied_checksum=None,
                        status="not_tracked",
                    )
                    for file in files
                ],
            )

        ledger_available, applied_records = self.ledger.list_applied()
        applied_by_version = {record.version: record for record in applied_records}
        items: list[MigrationStatusItem] = []
        for file in files:
            record = applied_by_version.get(file.version)
            if record is None:
                item_status = "pending" if ledger_available else "not_tracked"
                items.append(
                    MigrationStatusItem(
                        version=file.version,
                        filename=file.filename,
                        checksum=file.checksum,
                        applied_checksum=None,
                        status=item_status,
                    )
                )
                continue

            item_status = "applied" if record.checksum == file.checksum else "checksum_mismatch"
            items.append(
                MigrationStatusItem(
                    version=file.version,
                    filename=file.filename,
                    checksum=file.checksum,
                    applied_checksum=record.checksum,
                    status=item_status,
                    applied_at=record.applied_at,
                )
            )

        overall_status = _overall_status(ledger_available=ledger_available, items=items)
        return MigrationStatus(
            storage_backend=self.storage_backend,
            ledger_available=ledger_available,
            status=overall_status,
            migrations=items,
        )


def discover_migration_files(migrations_dir: Path) -> list[MigrationFile]:
    if not migrations_dir.exists():
        return []

    files: list[MigrationFile] = []
    for path in sorted(migrations_dir.glob("*.sql")):
        version = path.name.split("_", maxsplit=1)[0]
        files.append(
            MigrationFile(
                version=version,
                filename=path.name,
                checksum=sha256(path.read_bytes()).hexdigest(),
            )
        )
    return files


def _overall_status(*, ledger_available: bool, items: list[MigrationStatusItem]) -> str:
    if not ledger_available:
        return "untracked"
    statuses = {item.status for item in items}
    if "checksum_mismatch" in statuses:
        return "checksum_mismatch"
    if "pending" in statuses:
        return "pending"
    return "up_to_date"
