# Project implementation and testing guide

## Environment

- Use Python 3.13+ and `uv`.
- Install/sync dependencies with `uv sync --extra dev`.
- Tests use `jewel.settings_tests` from `pytest.ini` and SQLite by default.

## Check ownership

Implementers run only focused tests for their packet:

```shell
uv run pytest -q path/to/relevant_test.py
```

Use `manage.py check` in the implementation packet only when changing models,
admin, URLs, settings, or Django wiring. Migration-state checks belong to the
reviewer for model/migration packets. Test files are discovered as `tests.py`,
`test_*.py`, and `*_tests.py`.

Reviewers run the relevant pre-commit hooks and broader checks. Prefer:

```shell
prek run --files path/to/changed/files
```

The orchestrator does not repeat reviewer checks unless files changed afterward
or a result is ambiguous.

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

Use the repository's `prek` Ruff hooks for linting and formatting; do not
introduce Black/isort configuration or run unrelated formatters.

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
- Do not push or create a pull request unless explicitly requested.

## Commits

- After a packet passes implementation and review checks, the orchestrator may commit that packet on the dedicated branch.
- Keep one focused commit per verified packet; do not mix unrelated or unverified changes.
- Use the `caveman-commit` skill to generate a terse Conventional Commits message before committing.
- Never commit secrets, generated local databases, or unrelated worktree changes.
