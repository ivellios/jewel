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
