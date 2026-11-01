# jewel
Python/Django application for storing and processing games library

# Development

## Local Development with Docker (Recommended)

Requirements:
- Docker
- Docker Compose

### Installation

1. Clone repository
2. Build and start the services:
   ```shell
   docker compose up --build
   ```
3. Create superuser (in a new terminal):
   ```shell
   docker compose exec web uv run manage.py createsuperuser
   ```
4. Access the application at http://localhost:8000

### Managing the Docker environment

- **Start services**: `docker compose up`
- **Stop services**: `docker compose down`
- **View logs**: `docker compose logs web` or `docker compose logs db`
- **Run management commands**: `docker compose exec web uv run manage.py <command>`
- **Access Django shell**: `docker compose exec web uv run manage.py shell`

## Local Development without Docker

Requirements:
- uv
- Python 3.13+

### Installation

1. Clone repository
2. Install dependencies (including development tooling): `uv sync --extra dev`
3. Run migration for the project `uv run manage.py migrate`
4. Create your superuser `uv run manage.py createsuperuser`
5. Run the server `uv run manage.py runserver`

## Code formatting

The code is formatted using **Ruff** (replacement for Black + isort + Flake8).

Install and run hooks with **prek**:

```shell
# Install hooks (creates .git/hooks)
prek install

# Run all hooks on every tracked file
prek run --all-files

# Run a single hook
prek run ruff
```

### Developer commands

Run the reusable commands with `make` (they use the same scopes as CI):

```shell
# Run quality fixes (lint auto-fix + format)
make quality-fix

# Check quality without modifying files
make quality-check

# Run type checking
make type-check

# Run the full test suite
make test
```

### Individual tools

```shell
# Lint (auto-fix when possible)
uv run ruff check --fix games csv_importer steam abstract jewel

# Format (replaces Black)
uv run ruff format games csv_importer steam abstract jewel

# Django system checks
uv run python manage.py check
```

# Loading data

## Loading games

**With Docker:**
```shell
docker compose exec web uv run manage.py import_csv_data data.csv
```

**Without Docker:**
```shell
uv run manage.py import_csv_data data.csv
```

## Loading Steam games data

**With Docker:**
```shell
docker compose exec web uv run manage.py load_steam_library
```

**Without Docker:**
```shell
uv run manage.py load_steam_library
```

## Matching games with Steam and pulling more details

**With Docker:**
```shell
docker compose exec web uv run manage.py match_steam_games
```

**Without Docker:**
```shell
uv run manage.py match_steam_games
```

## Synchronising BoardGameGeek collection

**With Docker:**
```shell
docker compose exec web uv run manage.py sync_bgg_collection
```

**Without Docker:**
```shell
uv run manage.py sync_bgg_collection
```

### Configuration

Required settings (added to `settings.py` and `.env` / `.env.example`):

| Setting | Description | Default |
|---|---|---|
| `BGG_ACCESS_TOKEN` | BGG API access token (required) | — |
| `BGG_USER_NAME` | BGG user name whose collection to sync (required) | — |
| `BGG_API_URL` | BGG API base URL | `https://api.boardgamegeek.com` |
| `BGG_REQUEST_TIMEOUT` | Request timeout in seconds | `30` |

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Full successful reconciliation — all collection items processed without errors. |
| `1` | Partial reconciliation — collection fetch succeeded but some per-item detail fetches failed. |
| `2` | Failed reconciliation — the collection fetch itself failed (network / credential error). |

### Operational assumptions

* **Daily scheduled run** — designed for one cron/system-timer execution per day.
* **Idempotent** — repeated runs create new `BGGSyncRun` records and update/create the same `BoardGame` / `BGGMetadata` rows without duplication.
* **Read-only** — never writes to BGG, never schedules periodic tasks, never touches play history.

### Key semantics

* **Quantity / edition / name** — local editable fields (`name`, `language`, `edition_label`, `condition`, `storage`, `purchase_date`) are preserved across sync runs; imported fields (owned, rating, bgg metadata) are updated.
* **Expansion-with-base rule** — `BGGExpansion` rows are created only when both the expansion and its parent base `BGGMetadata` exist; orphan expansions (base not yet imported) are silently skipped.
* **Quantity deduplication** — a single `BoardGame` is created per `bgg_id` across the entire collection; when multiple collection entries share the same `bgg_id`, the last entry wins (ownership update).
* **Local-only preservation** — games with `imported=False` are never touched or removed.
* **Partial / fetch failure safety** — per-item detail fetch failures are recorded but do not stop the run; the game is created with `metadata=None`. A failed collection fetch (network / credential error) sets `fetch_successful=False`, which **never** removes existing copies.
* **Removal / restoration** — missing imported copies are soft-removed (`removed=True`) only when a full collection fetch succeeds; reappearing copies are restored.

### Integration tests

Fifteen scenarios in `boardgames/__tests__/test_sync_integration.py`:

1. First import (full success)
2. Repeated import (idempotent — new `BGGSyncRun`, updated `BoardGame`)
3. Distinct BGG IDs / editions — distinct copies
4. Quantity no-duplication (same `bgg_id`, multiple entries → single copy)
5. Local-only game — unaffected by sync
6. Local overrides — editable fields preserved
7. Expansion with / without base — `BGGExpansion` rows
8. Update — re-importing updates existing `BoardGame`
9. Removal — missing imported copies soft-removed
10. Restoration — reappearing copies restored
11. Partial item failure — some detail fetches fail, `BoardGame.metadata=None`
12. Failed collection fetch — network error, no copies removed
13. Persisted run diagnostics — `BGGSyncRun` with full counters / diagnostics
14. API contract — serializer fields match `BoardGame` exposed fields
15. Admin contract — read-only permissions on all admin classes

## Loading demo fixture (development data only)

A pre-seeded demo fixture is provided for local development and testing.
It contains 6 deterministic games across multiple platforms and vendors.

```shell
uv run manage.py loaddata demo_games
```

The fixture lives in `games/fixtures/demo_games.json` and covers:
- 4 platforms (PC, PlayStation 5, Nintendo Switch, Xbox)
- 5 vendors (Steam, GOG, Nintendo eShop, PlayStation Store, Microsoft Store)
- 6 genres, 6 games with varied metadata

**With Docker:**
```shell
docker compose exec web uv run manage.py loaddata demo_games
```

> [!IMPORTANT]
> This data is for local development/demo use only. It creates the `admin`
> superuser with password `password` and should be loaded into a disposable
> development database.
