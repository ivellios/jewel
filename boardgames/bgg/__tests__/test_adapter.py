"""Focused adapter tests — fully mocked, no live network calls."""

import dataclasses

import pytest

from boardgames.bgg import (
    BGGAdapter,
    BGGCollectionRecord,
    BGGDetailRecord,
    BGGPlaysRecord,
)
from boardgames.bgg.errors import (
    BGGCredentialMissingError,
    BGGNetworkError,
    BGGNotFoundError,
)

# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


def _make_board_game_data(
    bgg_id: int = 12345,
    name: str = "Terra Mystica",
    year: int | None = 2012,
    **extra: object,
) -> dict:
    stats = {
        "rating_bayes_average": 4.12,
        "rating_average": 4.35,
        "rating_median": 4.5,
        "rating_stddev": 0.8,
        "rating_num_weights": 2.8,
        "users_rated": 45000,
        "bgg_rank": 4,
        "boardgame_rank": 4,
    }
    return {
        "id": bgg_id,
        "name": name,
        "yearpublished": year,
        "minplayers": 2,
        "maxplayers": 4,
        "playingtime": 120,
        "minplaytime": 90,
        "maxplaytime": 150,
        "designers": ["Stefan Feld"],
        "publishers": ["Clemson University"],
        "mechanics": ["Area Influence", "Set Collection"],
        "categories": ["Farming", "Strategy"],
        "thumbnail": "https://thumb.example.com/tm.jpg",
        "image": "https://img.example.com/tm.jpg",
        "description": "A fantasy civilization game.",
        "users_owned": 12000,
        "stats": stats,
        "expansions": [
            {"id": 11111, "name": "AI Expansion"},
            {"id": 22222, "name": "Scorched Earth"},
        ],
        "expands": [{"id": 33333, "name": "Base game variant"}],
        **extra,
    }


def _make_collection_game_data(
    bgg_id: int = 12345, name: str = "Terra Mystica", **extra: object
) -> dict:
    stats = {
        "rating_bayes_average": 4.12,
        "rating_average": 4.35,
        "rating_median": 4.5,
        "rating_stddev": 0.8,
        "users_rated": 45000,
        "bgg_rank": 4,
        "boardgame_rank": 4,
    }
    return {
        "id": bgg_id,
        "name": name,
        "stats": stats,
        "numplays": 5,
        "owned": 1,
        "prev_owned": 0,
        "wishlist": 0,
        "wishlist_priority": 3,
        "want": 0,
        "want_to_play": 0,
        "want_to_buy": 1,
        "preordered": 0,
        "for_trade": 0,
        "comment": "Great game!",
        "lastmodified": "2024-01-15",
        **extra,
    }


def _patch_board_game(mock_client, game_data: dict) -> None:
    """Apply a mock ``BoardGame`` object to *mock_client.game*."""
    from boardgamegeek.objects import BoardGame

    mock_client.game.return_value = BoardGame(game_data)


def _patch_collection(mock_client, items: list[dict]) -> None:
    """Apply a mock ``Collection`` to *mock_client.collection*."""
    from boardgamegeek.objects import Collection

    collection_data = {"owner": "testuser", "items": items}
    mock_client.collection.return_value = Collection(collection_data)


def _patch_plays(mock_client, plays_count: int = 100) -> None:
    """Apply a mock ``Plays`` object to *mock_client.plays*."""
    from boardgamegeek.objects import Plays

    mock_client.plays.return_value = Plays(
        {
            "plays_count": plays_count,
            "plays": [
                {
                    "id": 1,
                    "date": "2024-01-01",
                    "players": "2",
                },
            ],
        }
    )


def _patch_batch(mock_client, game_data_list: list[dict]) -> None:
    """Apply a mock ``list[BoardGame]`` to *mock_client.game_list*."""
    from boardgamegeek.objects import BoardGame

    mock_client.game_list.return_value = [BoardGame(gd) for gd in game_data_list]


def _patch_search(mock_client, search_data_list: list[dict]) -> None:
    """Apply a mock ``list[SearchResult]`` to *mock_client.search*."""
    from boardgamegeek.objects.search import SearchResult

    mock_client.search.return_value = [SearchResult(sd) for sd in search_data_list]


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


@pytest.fixture
def mock_client(monkeypatch):
    """Return a mock ``BGGClient`` ready for patching."""
    from unittest.mock import MagicMock

    mc = MagicMock()
    monkeypatch.setattr("boardgames.bgg.adapter.BGGClient", lambda *a, **kw: mc)
    return mc


@pytest.fixture
def adapter(mock_client):
    """Adapter instance with mocked client."""
    return BGGAdapter(access_token="test-token")  # noqa: S106 - test fixture, not real credentials.


# -----------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------


class TestCredentialMissing:
    """Missing access_token raises a deterministic error."""

    def test_no_token_raises_deterministic_error(self):
        with pytest.raises(BGGCredentialMissingError):
            BGGAdapter(access_token="")

    def test_no_token_empty_string(self):
        with pytest.raises(BGGCredentialMissingError):
            BGGAdapter(access_token="")


class TestGetDetail:
    """Detail fetch normalises a ``BoardGame``."""

    def test_success(self, adapter, mock_client):
        data = _make_board_game_data()
        _patch_board_game(mock_client, data)

        result = adapter.get_detail(bgg_id=12345)

        assert isinstance(result, BGGDetailRecord)
        assert result.bgg_id == 12345
        assert result.name == "Terra Mystica"
        assert result.year == 2012
        assert result.min_players == 2
        assert result.max_players == 4
        assert result.playing_time == 120
        assert result.designers == "Stefan Feld"
        assert result.designers_list == ("Stefan Feld",)
        assert result.mechanics == "Area Influence, Set Collection"
        assert result.mechanics_list == ("Area Influence", "Set Collection")
        assert result.categories == "Farming, Strategy"
        assert result.categories_list == ("Farming", "Strategy")
        assert result.rating_bayes_average == 4.12
        assert result.rating_average == 4.35
        assert result.rating_median == 4.5
        assert result.rating_stddev == 0.8
        assert result.rating_num_weights == 2.8
        assert result.bgg_rank == 4
        assert result.boardgame_rank == 4
        assert result.users_rated == 45000
        assert result.users_owned == 12000
        assert result.thumbnail == "https://thumb.example.com/tm.jpg"
        assert result.image == "https://img.example.com/tm.jpg"
        assert result.description == "A fantasy civilization game."
        assert result.expansions == (11111, 22222)
        assert result.expands == (33333,)
        assert result.families == ()
        assert result.alternative_names == ()

    def test_missing_optional_fields(self, adapter, mock_client):
        """Fields absent from BGG data normalise to None / empty."""
        data = {
            "id": 99999,
            "name": "Mystery Game",
            "stats": {
                "users_rated": 100,
                "bgg_rank": None,
                "boardgame_rank": None,
            },
        }
        _patch_board_game(mock_client, data)

        result = adapter.get_detail(bgg_id=99999)

        assert result.min_players is None
        assert result.max_players is None
        assert result.playing_time is None
        assert result.year is None
        assert result.designers is None
        assert result.designers_list == ()
        assert result.bgg_rank is None
        assert result.users_owned is None
        assert result.thumbnail is None
        assert result.image is None
        assert result.expansions == ()
        assert result.expands == ()

    def test_not_found_raises_adapter_error(self, adapter, mock_client):
        from boardgamegeek import BGGItemNotFoundError

        mock_client.game.side_effect = BGGItemNotFoundError("not found")

        with pytest.raises(BGGNotFoundError):
            adapter.get_detail(bgg_id=99999)

    def test_network_error_raises_network_error(self, adapter, mock_client):
        from boardgamegeek import BGGApiError

        mock_client.game.side_effect = BGGApiError("timeout")

        with pytest.raises(BGGNetworkError):
            adapter.get_detail(bgg_id=12345)


class TestGetCollection:
    """Collection fetch normalises ``CollectionBoardGame`` objects."""

    def test_success(self, adapter, mock_client):
        item_data = _make_collection_game_data()
        _patch_collection(mock_client, [item_data])

        results = adapter.get_collection(user_name="testuser")

        assert len(results) == 1
        record = results[0]
        assert isinstance(record, BGGCollectionRecord)
        assert record.bgg_id == 12345
        assert record.name == "Terra Mystica"
        assert record.numplays == 5
        assert record.owned is True
        assert record.wishlist_priority == 3
        assert record.want_to_buy is True
        assert record.comment == "Great game!"
        assert record.last_modified == "2024-01-15"

    def test_empty_collection(self, adapter, mock_client):
        _patch_collection(mock_client, [])

        results = adapter.get_collection(user_name="testuser")

        assert results == ()

    def test_filters_passed_to_client(self, adapter, mock_client):
        _patch_collection(mock_client, [])

        adapter.get_collection(
            user_name="testuser",
            ids=[12345, 67890],
            rated=True,
            min_rating=3.5,
        )

        mock_client.collection.assert_called_once_with(
            user_name="testuser",
            ids=[12345, 67890],
            rated=True,
            min_rating=3.5,
        )

    def test_not_found_error(self, adapter, mock_client):
        from boardgamegeek import BGGItemNotFoundError

        mock_client.collection.side_effect = BGGItemNotFoundError("no user")

        with pytest.raises(BGGNotFoundError):
            adapter.get_collection(user_name="nonexistent")


class TestGetPlays:
    """Plays fetch normalises aggregated play data."""

    def test_success(self, adapter, mock_client):
        _patch_plays(mock_client, plays_count=100)

        result = adapter.get_plays(bgg_id=12345)

        assert isinstance(result, BGGPlaysRecord)
        assert result.bgg_id == 12345
        assert result.plays_count == 100
        assert len(result.play_sessions) == 1
        assert result.play_sessions[0]["id"] == 1
        assert result.play_sessions[0]["date"] == "2024-01-01"

    def test_empty_plays(self, adapter, mock_client):
        from boardgamegeek.objects import Plays

        mock_client.plays.return_value = Plays({"plays_count": 0})

        result = adapter.get_plays(bgg_id=12345)

        assert result.plays_count == 0
        assert result.play_sessions == ()

    def test_by_name(self, adapter, mock_client):
        _patch_plays(mock_client)

        adapter.get_plays(name="Terra Mystica")

        mock_client.plays.assert_called_once_with(
            name="Terra Mystica",
            game_id=None,
            min_date=None,
            max_date=None,
            subtype="boardgame",
        )

    def test_not_found_error(self, adapter, mock_client):
        from boardgamegeek import BGGItemNotFoundError

        mock_client.plays.side_effect = BGGItemNotFoundError("no plays")

        with pytest.raises(BGGNotFoundError):
            adapter.get_plays(bgg_id=12345)


class TestGetExpansions:
    """Expansion fetch resolves expansions and expanded-by relations."""

    def test_success(self, adapter, mock_client):
        from boardgamegeek.objects import BoardGame

        game_data = _make_board_game_data()
        _patch_board_game(mock_client, game_data)
        # Also patch game calls for expansion lookups
        expansion_data = _make_board_game_data(bgg_id=11111, name="AI Expansion")
        expansion_data2 = _make_board_game_data(bgg_id=22222, name="Scorched Earth")
        expansion_expands_data = _make_board_game_data(
            bgg_id=33333, name="Base game variant"
        )

        # Second and third calls (expansion lookups)
        mock_client.game.side_effect = [
            BoardGame(game_data),  # original call
            BoardGame(expansion_data),  # expansion 11111
            BoardGame(expansion_data2),  # expansion 22222
            BoardGame(expansion_expands_data),  # expands 33333
        ]

        result = adapter.get_expansions(bgg_id=12345)

        assert len(result) == 3
        assert isinstance(result, tuple)
        names = [r.name for r in result]
        assert "AI Expansion" in names
        assert "Scorched Earth" in names
        assert "Base game variant" in names

    def test_empty_expansions(self, adapter, mock_client):
        """No expansions = empty tuple."""
        data = _make_board_game_data(expansions=[], expands=[])
        _patch_board_game(mock_client, data)

        result = adapter.get_expansions(bgg_id=12345)

        assert result == ()

    def test_missing_expansion_id_fallback(self, adapter, mock_client):
        """When an expansion fetch fails, store the ID with empty name."""

        game_data = _make_board_game_data(
            bgg_id=12345,
            expansions=[],  # override: no expansions
            expands=[],  # override: no expands
        )
        _patch_board_game(mock_client, game_data)

        result = adapter.get_expansions(bgg_id=12345)

        assert result == ()


class TestGetBatch:
    """Batch fetch normalises multiple games."""

    def test_success(self, adapter, mock_client):
        data_list = [
            _make_board_game_data(bgg_id=1000, name="Game A"),
            _make_board_game_data(bgg_id=2000, name="Game B"),
        ]
        _patch_batch(mock_client, data_list)

        result = adapter.get_batch(game_ids=[1000, 2000])

        assert len(result) == 2
        assert isinstance(result, tuple)
        assert result[0].bgg_id == 1000
        assert result[0].name == "Game A"
        assert result[1].bgg_id == 2000
        assert result[1].name == "Game B"

    def test_empty_id_list(self, adapter, mock_client):
        result = adapter.get_batch(game_ids=[])

        assert result == ()
        mock_client.game_list.assert_not_called()

    def test_not_found_error(self, adapter, mock_client):
        from boardgamegeek import BGGItemNotFoundError

        mock_client.game_list.side_effect = BGGItemNotFoundError("batch not found")

        with pytest.raises(BGGNotFoundError):
            adapter.get_batch(game_ids=[1000, 2000])


class TestSearch:
    """Search fetch normalises ``SearchResult`` objects."""

    def test_success(self, adapter, mock_client):
        search_data = [
            {"id": 100, "name": "Catan", "type": "boardgame", "yearpublished": 1995},
            {
                "id": 200,
                "name": "Ticket to Ride",
                "type": "boardgame",
                "yearpublished": 2004,
            },
        ]
        _patch_search(mock_client, search_data)

        result = adapter.search(query="Catan")

        assert len(result) == 2
        assert result[0].bgg_id == 100
        assert result[0].name == "Catan"
        assert result[0].type == "boardgame"
        assert result[0].year == 1995

    def test_empty_results(self, adapter, mock_client):
        _patch_search(mock_client, [])

        result = adapter.search(query="nonexistent game xyz")

        assert result == ()

    def test_type_from_search_result(self, adapter, mock_client):
        search_data = [{"id": 500, "name": "BGG Board Game", "type": "boardgame"}]
        _patch_search(mock_client, search_data)

        result = adapter.search(query="test")

        assert result[0].type == "boardgame"

    def test_not_found_error(self, adapter, mock_client):
        from boardgamegeek import BGGItemNotFoundError

        mock_client.search.side_effect = BGGItemNotFoundError("no results")

        with pytest.raises(BGGNotFoundError):
            adapter.search(query="something")


class TestRecordImmutability:
    """Jewel-owned records are immutable (frozen dataclasses)."""

    def test_detail_record_is_frozen(self):
        rec = BGGDetailRecord(
            bgg_id=1,
            name="Test",
            year=None,
            min_players=None,
            max_players=None,
            playing_time=None,
            min_playing_time=None,
            max_playing_time=None,
            designers=None,
            publishers=None,
            mechanics=None,
            categories=None,
            rating_bayes_average=None,
            rating_average=None,
            rating_median=None,
            rating_stddev=None,
            rating_num_weights=None,
            bgg_rank=None,
            boardgame_rank=None,
            users_rated=None,
            users_owned=None,
            thumbnail=None,
            image=None,
            description=None,
        )
        with pytest.raises((dataclasses.FrozenInstanceError, TypeError)):
            rec.bgg_id = 999

    def test_collection_record_is_frozen(self):
        rec = BGGCollectionRecord(
            bgg_id=1,
            name="Test",
            rating=None,
            numplays=0,
            owned=False,
            prev_owned=False,
            wishlist=False,
            wishlist_priority=None,
            want=False,
            want_to_play=False,
            want_to_buy=False,
            preordered=False,
            for_trade=False,
            comment=None,
            last_modified=None,
            min_players=None,
            max_players=None,
            playing_time=None,
            min_playing_time=None,
            max_playing_time=None,
            year=None,
            thumbnail=None,
            image=None,
            bgg_rank=None,
            boardgame_rank=None,
            rating_bayes_average=None,
            rating_average=None,
            rating_median=None,
            rating_stddev=None,
            users_rated=None,
        )
        with pytest.raises((dataclasses.FrozenInstanceError, TypeError)):
            rec.bgg_id = 999
