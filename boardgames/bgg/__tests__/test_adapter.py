"""Pure BGG normalization tests using plain response fixtures only."""

import dataclasses

import pytest

from boardgames.bgg import (
    BGGCollectionRecord,
    BGGDetailRecord,
    BGGLocalizedVersionRecord,
    BGGPlaySessionRecord,
    normalize_batch_item,
    normalize_collection_item,
    normalize_detail,
    normalize_plays,
)


def test_detail_normalizes_values_and_relations_without_io():
    record = normalize_detail(
        {
            "id": "123",
            "name": "  Terra Mystica  ",
            "yearpublished": "2012",
            "designers": ["Stefan Feld", ""],
            "expansions": [{"id": "22"}, {"id": None}, {"id": "22"}],
            "stats": {"rating_average": "4.35", "bgg_rank": "4"},
        }
    )
    assert record == BGGDetailRecord(
        bgg_id=123,
        item_type=None,
        name="Terra Mystica",
        year=2012,
        min_players=None,
        max_players=None,
        playing_time=None,
        min_playing_time=None,
        max_playing_time=None,
        designers="Stefan Feld",
        publishers=None,
        mechanics=None,
        categories=None,
        rating_bayes_average=None,
        rating_average=4.35,
        rating_median=None,
        rating_stddev=None,
        rating_num_weights=None,
        bgg_rank=4,
        boardgame_rank=None,
        users_rated=None,
        users_owned=None,
        thumbnail=None,
        image=None,
        description=None,
        bgg_url=None,
        plays_count=None,
        expansions=(22, 22),
        designers_list=("Stefan Feld",),
    )


def test_detail_normalizes_localized_version_titles():
    record = normalize_detail(
        {
            "id": 378758,
            "localized_versions": [
                {
                    "id": "667143",
                    "language": "Polish",
                    "canonical_name": "Podziemne Imperium",
                }
            ],
        }
    )

    assert record.localized_versions == (
        BGGLocalizedVersionRecord(
            version_id=667143, language="Polish", title="Podziemne Imperium"
        ),
    )


@pytest.mark.parametrize(
    ("flags", "expected_type"),
    [
        ({"expansion": True}, "boardgameexpansion"),
        ({"accessory": True}, "boardgameaccessory"),
        ({"type": "boardgame", "expansion": True}, "boardgame"),
    ],
)
def test_detail_infers_item_type_from_vendor_flags(flags, expected_type):
    assert normalize_detail({"id": "123", **flags}).item_type == expected_type


def test_collection_normalizes_missing_values_and_quantity():
    record = normalize_collection_item(
        {
            "id": "123",
            "numplays": None,
            "owned": "1",
            "want_to_buy": "false",
            "numowned": "2",
            "stats": {"users_rated": "not-a-number"},
        }
    )

    assert record.numplays == 0
    assert record.owned is True
    assert record.want_to_buy is False
    assert record.quantity == 2
    assert record.users_rated is None


def test_collection_normalizes_selected_owned_version():
    record = normalize_collection_item(
        {
            "id": "9209",
            "name": "Ticket to Ride",
            "version": {
                "id": "123456",
                "name": "Wsiąść do Pociągu",
                "language": "Polish",
                "year": "2019",
                "publisher": "Rebel",
            },
        }
    )

    assert record.bgg_id == 9209
    assert record.version_id == 123456
    assert record.version_name == "Wsiąść do Pociągu"
    assert record.version_language == "Polish"
    assert record.version_year == 2019
    assert record.version_publisher == "Rebel"


def test_plays_are_immutable_jewel_records():
    record = normalize_plays(
        {
            "plays_count": "1",
            "plays": [{"id": "5", "date": "2024-01-01", "players": ["A", "B"]}],
        },
        bgg_id=123,
        name="Game",
    )

    assert record.play_sessions == (
        BGGPlaySessionRecord(play_id=5, played_on="2024-01-01", players=("A", "B")),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.play_sessions[0].play_id = 10


@pytest.mark.parametrize("raw", [{}, {"id": 0}, {"id": "unknown"}])
def test_required_ids_are_explicit(raw):
    with pytest.raises(ValueError, match="positive id"):
        normalize_batch_item(raw)


def test_normalized_records_are_frozen():
    record = normalize_collection_item({"id": 1})
    assert isinstance(record, BGGCollectionRecord)
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.quantity = 3


def test_normalizers_accept_plain_fixture_objects_and_never_construct_a_client(
    monkeypatch,
):
    class FixtureRelation:
        id = "3"

    class FixtureDetail:
        id = "2"
        name = "Fixture game"
        year = "2020"
        stats = {"rating_average": "7.2"}
        expansions = [FixtureRelation()]

    def unexpected_client_construction(*args, **kwargs):
        raise AssertionError("normalization must not construct BGGClient")

    monkeypatch.setattr(
        "boardgames.bgg.client.BGGClient.__init__",
        unexpected_client_construction,
    )

    assert normalize_detail(FixtureDetail()).expansions == (3,)


def test_batch_and_search_records_normalize_deterministically():
    record = normalize_batch_item(
        {"id": "5", "name": "  Catan ", "type": "boardgame", "year": "1995"}
    )
    assert record.bgg_id == 5
    assert record.name == "Catan"
    assert normalize_batch_item({"id": 5, "year": "not-a-year"}).year is None
