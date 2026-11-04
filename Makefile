.PHONY: quality-fix quality-check type-check test

# Quality coverage: ruff + format for every path.
# mypy scope is intentionally narrower (see ci.yml and .pre-commit-config.yaml).
QUALITY_PATHS = games csv_importer steam abstract jewel boardgames

# Narrow mypy scope: all modules now included (boardgames completed in Packet 14).
MYPY_PATHS = games csv_importer steam abstract jewel boardgames

quality-fix:
	uv run ruff check --fix $(QUALITY_PATHS)
	uv run ruff format $(QUALITY_PATHS)

quality-check:
	uv run ruff check $(QUALITY_PATHS)
	uv run ruff format --check $(QUALITY_PATHS)

type-check:
	uv run mypy --config-file pyproject.toml $(MYPY_PATHS)

test:
	uv run pytest -v
