.PHONY: install dev test lint typecheck regression demo dispatch-webhooks verify verify-tenant-rls migration-status migration-baseline migration-apply run

install:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -e ".[dev]"

dev:
	. .venv/bin/activate && uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000

test:
	. .venv/bin/activate && pytest

lint:
	. .venv/bin/activate && ruff check .

typecheck:
	. .venv/bin/activate && mypy apps --explicit-package-bases

regression:
	. .venv/bin/activate && python scripts/run_regression_eval.py

demo:
	. .venv/bin/activate && python scripts/run_demo_flow.py

dispatch-webhooks:
	. .venv/bin/activate && python scripts/dispatch_webhooks.py --tenant-id $${TENANT_ID:-default} --limit $${LIMIT:-100}

verify-tenant-rls:
	. .venv/bin/activate && python scripts/verify_tenant_rls.py

migration-status:
	. .venv/bin/activate && python scripts/manage_migrations.py status

migration-baseline:
	. .venv/bin/activate && python scripts/manage_migrations.py baseline

migration-apply:
	. .venv/bin/activate && python scripts/manage_migrations.py apply

verify: lint typecheck test regression

run:
	. .venv/bin/activate && uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
