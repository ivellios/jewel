# jewel
Python/Django application for storing and processing games library

# Development

Requirements:
- uv

## Installation

1. Clone repository
1. Run migration for the project `uv run manage.py migrate`
1. Create your superuser `uv run manage.py createsuperuser`
1. Run the server `uv run manage.py runserver`

## Code formatting

The code is formatted using the black library.

`uv run black .`

# Loading data

## Loading games

```shell
$ uv run manage.py load_csv_data data.csv
```

## Loading Steam games data

```shell
$ uv run manage.py load_steam_library
```

## Matching games with Steam and pulling more details

```shell
$ uv run manage.py pull_steam_data
```
