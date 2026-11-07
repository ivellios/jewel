"""Focused tests for the raw BGG transport boundary."""

from unittest.mock import MagicMock
from xml.etree import ElementTree

import pytest
from boardgamegeek import BGGApiError, BGGItemNotFoundError

from boardgames.bgg.client import DEFAULT_BGG_API_URL, BGGClient
from boardgames.bgg.errors import (
    BGGCredentialMissingError,
    BGGNetworkError,
    BGGNotFoundError,
)


@pytest.fixture
def vendor_client(monkeypatch):
    """Replace the vendor client without making a network call."""
    client = MagicMock()
    factory = MagicMock(return_value=client)
    monkeypatch.setattr("boardgames.bgg.client.BoardGameGeekClient", factory)
    return client, factory


@pytest.fixture
def token():
    """Provide a non-production credential for client construction."""
    return "test-token"


def test_client_uses_default_endpoint_and_timeout(vendor_client, token):
    client, factory = vendor_client

    transport = BGGClient(access_token=token, timeout=12.5)

    factory.assert_called_once_with(access_token=token, timeout=12.5)
    assert transport._timeout == 12.5
    assert DEFAULT_BGG_API_URL == "https://boardgamegeek.com/xmlapi2"
    assert client._thing_api_url == f"{DEFAULT_BGG_API_URL}/thing"


def test_client_honors_configured_endpoint(vendor_client, token):
    vendor, factory = vendor_client
    client = BGGClient(
        access_token=token,
        api_url="https://bgg.example.test/api/",
        timeout=12.5,
    )

    factory.assert_called_once_with(access_token=token, timeout=12.5)
    assert client._api_url == "https://bgg.example.test/api"
    assert vendor._collection_api_url == "https://bgg.example.test/api/collection"
    assert vendor._thing_api_url == "https://bgg.example.test/api/thing"


def test_client_returns_raw_vendor_response(vendor_client, token):
    vendor, _ = vendor_client
    raw_response = object()
    vendor.game.return_value = raw_response
    client = BGGClient(access_token=token)

    assert client.game(42) is raw_response
    vendor.game.assert_called_once_with(game_id=42)


def test_game_list_retains_localized_version_canonical_name(
    vendor_client, token, monkeypatch
):
    vendor, _ = vendor_client
    vendor.requests_session = object()
    vendor._retries = 3
    vendor._retry_delay = 0
    vendor._get_auth_headers.return_value = {"Authorization": "Bearer test-token"}
    xml = ElementTree.fromstring(  # noqa: S314 - trusted inline test fixture.
        '<items><item id="378758" type="boardgame"><versions>'
        '<item id="667143"><canonicalname value="Podziemne Imperium" />'
        '<link type="language" value="Polish" /></item>'
        "</versions></item></items>"
    )
    monkeypatch.setattr(
        "boardgames.bgg.client.request_and_parse_xml", lambda *a, **k: xml
    )
    game = MagicMock()
    game._data = {"id": 378758, "name": "Imperial Miners"}
    monkeypatch.setattr(
        "boardgames.bgg.client.create_game_from_xml", lambda *_a, **_k: game
    )

    result = BGGClient(access_token=token).game_list([378758])

    assert result[0]["name"] == "Imperial Miners"
    assert result[0]["localized_versions"] == [
        {
            "id": 667143,
            "language": "Polish",
            "canonical_name": "Podziemne Imperium",
        }
    ]


def test_game_list_extacts_poll_summary_from_batch_xml(
    vendor_client, token, monkeypatch
):
    """Mascarade: bestwith and BGG-typo recommmendedwith survive game_list."""
    vendor, _ = vendor_client
    vendor.requests_session = object()
    vendor._retries = 3
    vendor._retry_delay = 0
    vendor._get_auth_headers.return_value = {"Authorization": "Bearer test-token"}
    xml = ElementTree.fromstring(  # noqa: S314 - trusted inline test fixture.
        "<items>"
        '<item id="139030" type="boardgame"><name>Imperial Miners'
        '</name><poll-summary name="suggested_numplayers">'
        '<result name="bestwith" value="Best with 6–8 players" />'
        '<result name="recommmendedwith" value="Recommended with 4–11 players" />'
        "</poll-summary>"
        '<versions><item id="667143"><canonicalname value="Podziemne Imperium" />'
        '<link type="language" value="Polish" /></item></versions>'
        "</item></items>"
    )
    monkeypatch.setattr(
        "boardgames.bgg.client.request_and_parse_xml", lambda *a, **k: xml
    )
    game = MagicMock()
    game._data = {"id": 139030, "name": "Imperial Miners"}
    monkeypatch.setattr(
        "boardgames.bgg.client.create_game_from_xml", lambda *_a, **_k: game
    )

    result = BGGClient(access_token=token).game_list([139030])

    snp = result[0].get("suggested_numplayers")
    assert snp is not None
    # New format: plain mapping matching adapter's _poll_summary contract.
    assert snp["poll-summary"]["result"] == [
        {"name": "bestwith", "value": "Best with 6–8 players"},
        {"name": "recommmendedwith", "value": "Recommended with 4–11 players"},
    ]


def test_game_list_two_games_with_and_without_summary(
    vendor_client, token, monkeypatch
):
    """Per-game poll-summary: both games, one with Mascarade, one without."""
    vendor, _ = vendor_client
    vendor.requests_session = object()
    vendor._retries = 3
    vendor._retry_delay = 0
    vendor._get_auth_headers.return_value = {"Authorization": "Bearer test-token"}
    xml = ElementTree.fromstring(  # noqa: S314 - trusted inline test fixture.
        "<items>"
        '<item id="139030" type="boardgame"><name>Game A'
        '</name><poll-summary name="suggested_numplayers">'
        '<result name="bestwith" value="Best with 4" />'
        "</poll-summary>"
        "<versions></versions></item>"
        '<item id="456" type="boardgame"><name>Game B'
        "</name><versions></versions></item>"
        "</items>"
    )
    monkeypatch.setattr(
        "boardgames.bgg.client.request_and_parse_xml", lambda *a, **k: xml
    )
    game_a = MagicMock()
    game_a._data = {"id": 139030, "name": "Game A"}
    game_b = MagicMock()
    game_b._data = {"id": 456, "name": "Game B"}
    monkeypatch.setattr(
        "boardgames.bgg.client.create_game_from_xml",
        lambda e, *, game_id=None: game_a if game_id == 139030 else game_b,
    )

    result = BGGClient(access_token=token).game_list([139030, 456])

    assert len(result) == 2
    # Game A has Mascarade summary attached per-game.
    assert result[0]["suggested_numplayers"] == {
        "poll-summary": {
            "result": [{"name": "bestwith", "value": "Best with 4"}],
        },
    }
    # Game B has no poll-summary (None).
    assert result[1].get("suggested_numplayers") is None


def test_collection_returns_raw_items_not_the_vendor_wrapper(vendor_client, token):
    vendor, _ = vendor_client
    raw_item = object()
    vendor.collection.return_value = MagicMock(_items=(raw_item,))
    client = BGGClient(access_token=token)

    assert list(client.collection("player")) == [raw_item]
    vendor.collection.assert_called_once_with(user_name="player", ids=None)


def test_missing_credential_is_a_jewel_error():
    with pytest.raises(BGGCredentialMissingError):
        BGGClient(access_token="")


def test_vendor_not_found_maps_to_jewel_error(vendor_client, token):
    vendor, _ = vendor_client
    vendor.game.side_effect = BGGItemNotFoundError("missing")
    client = BGGClient(access_token=token)

    with pytest.raises(BGGNotFoundError):
        client.game(42)


def test_vendor_network_error_maps_to_jewel_error(vendor_client, token):
    vendor, _ = vendor_client
    vendor.game.side_effect = BGGApiError("unavailable")
    client = BGGClient(access_token=token)

    with pytest.raises(BGGNetworkError):
        client.game(42)
