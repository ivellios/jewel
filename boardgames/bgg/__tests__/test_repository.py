"""Focused tests for the high-level BGG repository boundary."""

from unittest.mock import MagicMock

from boardgames.bgg import BGGExpansionRecord, BGGRepository
from boardgames.bgg import repository as repository_module


def _repository_with(client: MagicMock, monkeypatch) -> BGGRepository:
    factory = MagicMock(return_value=client)
    monkeypatch.setattr("boardgames.bgg.repository.BGGClient", factory)
    return BGGRepository(access_token="test-token")  # noqa: S106 - test credential.


def test_repository_normalizes_detail_and_collection_raw_items(monkeypatch):
    client = MagicMock()
    client.game.return_value = {"id": "42", "name": " Detail game "}
    client.collection.return_value = (
        {"id": "42", "name": " Collection game ", "numowned": "2"},
    )
    repository = _repository_with(client, monkeypatch)

    detail = repository.get_detail(42)
    collection = repository.get_collection("player", ids=(42,), owned=True)

    assert detail.bgg_id == 42
    assert detail.name == "Detail game"
    assert collection[0].bgg_id == 42
    assert collection[0].name == "Collection game"
    assert collection[0].quantity == 2
    client.collection.assert_called_once_with(
        "player", ids=(42,), version=True, owned=True
    )


def test_collection_items_are_normalized_lazily(monkeypatch):
    client = MagicMock()
    raw_items = [
        {"id": str(bgg_id), "name": f"Game {bgg_id}"} for bgg_id in range(1, 4)
    ]
    client.collection.return_value = raw_items
    repository = _repository_with(client, monkeypatch)
    normalize = MagicMock(wraps=repository_module.normalize_collection_item)
    monkeypatch.setattr(repository_module, "normalize_collection_item", normalize)

    collection = repository.get_collection("player")

    assert len(collection) == 3
    assert normalize.call_count == 0
    assert next(iter(collection)).bgg_id == 1
    assert normalize.call_count == 1


def test_get_details_uses_bgg_multi_id_endpoint(monkeypatch):
    client = MagicMock()
    client.game_list.return_value = [{"id": "42"}, {"id": "43"}]
    repository = _repository_with(client, monkeypatch)

    details = repository.get_details((42, 43))

    assert [record.bgg_id for record in details] == [42, 43]
    client.game_list.assert_called_once_with((42, 43))


def test_repository_normalizes_plays_and_resolves_expansion_records(monkeypatch):
    client = MagicMock()
    client.plays.return_value = {
        "plays_count": "1",
        "plays": [{"id": "9", "date": "2024-01-01", "players": ["A"]}],
    }
    client.game.side_effect = [
        {"id": "42", "expansions": [{"id": "7"}], "expands": [{"id": "8"}]},
        {"id": "7", "name": "Expansion"},
        {"id": "8", "name": "Base game"},
    ]
    repository = _repository_with(client, monkeypatch)

    plays = repository.get_plays(42, name="Game")
    expansions = repository.get_expansions(42)

    assert plays.bgg_id == 42
    assert plays.plays_count == 1
    assert expansions == (
        BGGExpansionRecord(bgg_id=7, name="Expansion"),
        BGGExpansionRecord(bgg_id=8, name="Base game"),
    )


def test_repository_returns_a_jewel_record_when_related_detail_fails(monkeypatch):
    from boardgames.bgg.errors import BGGNotFoundError

    client = MagicMock()
    client.game.side_effect = [
        {"id": "42", "expansions": [{"id": "7"}]},
        BGGNotFoundError("missing"),
    ]
    repository = _repository_with(client, monkeypatch)

    assert repository.get_expansions(42) == (BGGExpansionRecord(bgg_id=7, name=None),)
