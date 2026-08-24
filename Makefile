.PHONY: sync lint format format-check typecheck test schemas schemas-check secret-scan audit ci

sync:
	uv sync --extra dev

lint:
	uv run ruff check .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

typecheck:
	uv run mypy

test:
	uv run pytest --cov=epistemic_loop --cov-report=term-missing

schemas:
	uv run python scripts/export_schemas.py

schemas-check: schemas
	git diff --exit-code -- schemas

secret-scan:
	uv run python scripts/secret_scan.py

audit:
	uv run --with pip-audit pip-audit

ci: lint format-check typecheck test schemas-check secret-scan audit
