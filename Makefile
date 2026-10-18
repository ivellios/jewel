.PHONY: quality-fix quality-check type-check test

QUALITY_PATHS = games csv_importer steam abstract jewel

quality-fix:
	uv run ruff check --fix $(QUALITY_PATHS)
	uv run ruff format $(QUALITY_PATHS)

quality-check:
	uv run ruff check $(QUALITY_PATHS)
	uv run ruff format --check $(QUALITY_PATHS)

type-check:
	uv run mypy --config-file pyproject.toml $(QUALITY_PATHS)

test:
	uv run pytest -v
