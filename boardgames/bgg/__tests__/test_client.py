"""Focused tests for the raw BGG transport boundary."""

from unittest.mock import MagicMock

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
