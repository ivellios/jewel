from datetime import datetime
from decimal import Decimal

import pytest

from abstract.games import GameInterface, GameOnPlatformInterface, PlatformInterface
from games.models import Game
from games.repositories import DjangoGameRepository


@pytest.fixture
def empty_game():
    class SimpleGame(GameInterface):
        id = None
        name = "Some game"
        platforms = []
        play_priority = None
        played = False
        controller_support = None
        max_players = None
        party_fit = None
        review = None
        notes = None
        genres = []
        price = None
        added = None
        vendor = None

    return SimpleGame()


@pytest.fixture
def simple_game():
    class SimpleGame(GameInterface):
        id = None
        name = "Some game"
        platforms = []
        play_priority = 5
        played = True
        controller_support = True
        max_players = 10
        party_fit = True
        review = 10
        notes = "Some notes"
        genres = []

    return SimpleGame()


@pytest.fixture
def simple_game_on_platform():
    class SimplePlatform(PlatformInterface):
        name = "Some platform"

    class SimpleGameOnPlatform(GameOnPlatformInterface):
        platform = SimplePlatform()
        added = datetime.now().date()
        identifier = "Some identifier"
        price = Decimal("5.55")
        vendor = None

    return SimpleGameOnPlatform()


def test_repository_create(empty_game):
    # given
    # when
    game, _ = DjangoGameRepository.create(empty_game)

    # then
    assert game.name == empty_game.name


def test_repository_create_simple_game(simple_game):
    # given
    # when
    game, _ = DjangoGameRepository.create(simple_game)

    # then
    assert game.name == simple_game.name
    assert game.play_priority == simple_game.play_priority
    assert game.played
    assert game.controller_support
    assert game.party_fit
    assert game.max_players == simple_game.max_players
    assert game.review == simple_game.review
    assert game.notes == simple_game.notes


def test_repository_remove_simple_game(simple_game):
    # given
    game, _ = DjangoGameRepository.create(simple_game)

    # when
    DjangoGameRepository.remove(game.id)

    # then
    assert not Game.objects.filter(pk=game.id).exists()


def test_repository_create_creates_platforms(simple_game_on_platform, simple_game):
    # given
    simple_game.platforms = [simple_game_on_platform]

    # when
    game, _ = DjangoGameRepository.create(simple_game)

    # then
    assert game.platforms.count() == 1
    assert game.platforms.first().name == simple_game_on_platform.platform.name


def test_repository_create_updates_existing_game(simple_game):
    # given
    game, _ = DjangoGameRepository.create(simple_game)

    # when
    game_updated, _ = DjangoGameRepository.create(simple_game)

    # then
    assert game.pk == game_updated.pk
