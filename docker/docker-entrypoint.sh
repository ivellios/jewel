#!/bin/bash -e
uv run manage.py migrate --noinput
uv run manage.py collectstatic --noinput
exec "$@"
