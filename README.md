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
2. Install dependencies: `uv sync`
3. Run migration for the project `uv run manage.py migrate`
4. Create your superuser `uv run manage.py createsuperuser`
5. Run the server `uv run manage.py runserver`

## Code formatting

The code is formatted using the black library.

`uv run black .`

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
docker compose exec web uv run manage.py pull_steam_data
```

**Without Docker:**
```shell
uv run manage.py pull_steam_data
```
