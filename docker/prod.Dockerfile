FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv (package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies (only core, no dev tools)
RUN uv sync --frozen

# Install uwsgi
RUN uv pip install uwsgi

# Copy application code
COPY . .

RUN chmod +x /app/docker/docker-entrypoint.sh

ENTRYPOINT ["/app/docker/docker-entrypoint.sh"]

# Expose port
EXPOSE 8000

CMD ["uv", "run", "uwsgi", "--http", "0.0.0.0:8000", "--module", "jewel.wsgi:application", "--master", "--processes", "4", "--threads", "2", "--static-map", "/static=/app/staticfiles", "--mime-file=/app/docker/uwsgi-mime.types"]
