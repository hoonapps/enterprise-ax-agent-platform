.PHONY: install dev test lint typecheck regression dispatch-webhooks verify run

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

dispatch-webhooks:
	. .venv/bin/activate && python scripts/dispatch_webhooks.py --tenant-id $${TENANT_ID:-default} --limit $${LIMIT:-100}

verify: lint typecheck test regression

run:
	. .venv/bin/activate && uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
