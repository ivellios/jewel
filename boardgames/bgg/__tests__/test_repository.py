"""Focused tests for the high-level BGG repository boundary."""

from unittest.mock import MagicMock

from boardgames.bgg import BGGExpansionRecord, BGGRepository


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
    client.collection.assert_called_once_with("player", ids=(42,), owned=True)


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
