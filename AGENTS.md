# Project implementation and testing guide

## Environment

- Use Python 3.13+ and `uv`.
- Install/sync dependencies with `uv sync --extra dev`.
- Tests use `jewel.settings_tests` from `pytest.ini` and SQLite by default.

## Minimum checks for an implementation packet

Run only the smallest relevant checks for the files changed:

```shell
uv run python manage.py check
uv run pytest -q path/to/relevant_test.py
uv run ruff check path/to/changed/files
uv run ruff format --check path/to/changed/files
```

Use `uv run pytest -q` for the full suite when the packet affects shared behavior. Test files are discovered as `tests.py`, `test_*.py`, and `*_tests.py`.

## Repository-wide checks

```shell
make test
make quality-check
make type-check
```

Equivalent commands are:

```shell
uv run pytest -v
uv run ruff check games csv_importer steam abstract jewel
uv run ruff format --check games csv_importer steam abstract jewel
uv run mypy --config-file pyproject.toml games csv_importer steam abstract jewel
```

Use Ruff for both linting and formatting; do not introduce Black/isort configuration or run unrelated formatters.

## Django and migrations

- Run Django commands through `uv run python manage.py ...`.
- Generate migrations with `uv run python manage.py makemigrations games`.
- Never hand-write migration operations, recreate tables, copy data, or edit historical migrations.
- Inspect generated migrations and SQL with `uv run python manage.py sqlmigrate games <number>`.
- Verify migration state with `uv run python manage.py showmigrations games` and `uv run python manage.py makemigrations games --check --dry-run`.
- Use a disposable/local database for migration and data-preservation checks.

## Implementation conventions

- Read nearby code and tests before editing; preserve existing API paths, response shapes, relations, and behavior unless the task requires otherwise.
- Update factories, fixtures, serializers, admin, templates, and tests together when renaming models.
- Keep tests focused on the changed behavior. The reviewer owns the full suite and repository-wide quality checks.
- Do not commit, push, reset, or create a pull request unless explicitly requested.
