# jewel
Python/Django application for storing and processing games library

# Development

## Installation

1. Clone repository
2. Install python with `pyenv install`
3. Create a virtualenv `pyenv virtualenv jewel`
4. Activate the virtualenv `pyenv activate jewel`
5. Install dependencies `pip install -r requirements.txt`
6. Run the server `./manage.py runserver`

## Code formatting

The code is formatted using the black library.

# Loading data

## Loading games

```shell
$ ./manage.py load_csv_data data.csv
```

## Loading Steam games data

```shell
$ ./manage.py load_steam_library
```

## Matching games with Steam and pulling more details

```shell
$ ./manage.py pull_steam_data
```
