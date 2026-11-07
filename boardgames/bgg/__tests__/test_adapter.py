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


def test_suggested_players_when_present():
    """Suggested poll data with best/recommended/notrecommended."""

    raw = {
        "id": "287843",
        "suggested_players": [
            {
                "numplayers": "1",
                "best": "42",
                "recommended": None,
                "notrecommended": "8",
            },
            {
                "numplayers": "2",
                "best": None,
                "recommended": "15",
                "notrecommended": "2",
            },
            {
                "numplayers": "3",
                "best": "100",
                "recommended": "30",
                "notrecommended": "0",
            },
            # Items with no votes are skipped.
            {"numplayers": "5"},
        ],
    }
    record = normalize_detail(raw)
    assert record.suggested_players == (
        {"numplayers": "1", "best": 42, "notrecommended": 8},
        {"numplayers": "2", "recommended": 15, "notrecommended": 2},
        {"numplayers": "3", "best": 100, "recommended": 30, "notrecommended": 0},
        {"numplayers": "5"},
    )


def test_suggested_players_with_actual_bgg_results_mapping():
    """Parse the actual BGG API results mapping structure."""

    raw = {
        "id": "287843",
        "suggested_players": {
            "total_votes": 360,
            "results": {
                "1": {"best_rating": 42, "recommended_rating": 10},
                "2": {"best_rating": 15, "not_recommended_rating": 2},
                "3": {
                    "best_rating": 100,
                    "recommended_rating": 30,
                    "not_recommended_rating": 0,
                },
                "4": {},
                "7+": {"best_rating": 5, "recommended_rating": 1},
                # Missing rating keys are simply omitted.
                "5": {"not_recommended_rating": 8},
            },
        },
    }
    record = normalize_detail(raw)
    assert record.suggested_players == (
        {"numplayers": "1", "best": 42, "recommended": 10},
        {"numplayers": "2", "best": 15, "notrecommended": 2},
        {"numplayers": "3", "best": 100, "recommended": 30, "notrecommended": 0},
        {"numplayers": "4"},
        {"numplayers": "7+", "best": 5, "recommended": 1},
        {"numplayers": "5", "notrecommended": 8},
    )


def test_suggested_players_missing_poll_key_returns_none():
    """When suggested_players is absent, the field is None."""

    record = normalize_detail({"id": "123"})
    assert record.suggested_players is None


def test_suggested_players_present_but_empty_results():
    """Present-but-empty results normalizes to empty tuple, not None."""

    raw = {
        "id": "999",
        "suggested_players": {
            "total_votes": 0,
            "results": {},
        },
    }
    record = normalize_detail(raw)
    assert record.suggested_players == ()


def test_suggested_players_with_malformed_entries_ignored():
    """Non-dict items and items with no valid data are skipped."""

    raw = {
        "id": "999",
        "suggested_players": ["not_a_dict", 42, {}],
    }
    record = normalize_detail(raw)
    assert record.suggested_players == ()


def test_batch_and_search_records_normalize_deterministically():
    record = normalize_batch_item(
        {"id": "5", "name": "  Catan ", "type": "boardgame", "year": "1995"}
    )
    assert record.bgg_id == 5
    assert record.name == "Catan"
    assert normalize_batch_item({"id": 5, "year": "not-a-year"}).year is None


def test_poll_summary_extracts_bestwith_and_recommendedwith():
    """Mascarade-style poll-summary results extraction."""

    raw = {
        "id": "139030",
        "suggested_numplayers": {
            "poll-summary": {
                "result": [
                    {"name": "bestwith", "value": "Best with 6–8 players"},
                    {
                        "name": "recommmendedwith",
                        "value": "Recommended with 4–11 players",
                    },
                ],
            },
        },
    }
    record = normalize_detail(raw)
    assert record.numplayers_summary == {
        "bestwith": "Best with 6–8 players",
        "recommendedwith": "Recommended with 4–11 players",
    }


def test_poll_summary_accepts_corrected_spelling():
    """When BGG uses the corrected 'recommendedwith' spelling, it is accepted."""

    raw = {
        "id": "139030",
        "suggested_numplayers": {
            "poll-summary": {
                "result": [
                    {"name": "bestwith", "value": "Best with 3 players"},
                    {"name": "recommendedwith", "value": "Recommended with 5 players"},
                ],
            },
        },
    }
    record = normalize_detail(raw)
    assert record.numplayers_summary == {
        "bestwith": "Best with 3 players",
        "recommendedwith": "Recommended with 5 players",
    }


def test_poll_summary_return_none_when_no_poll_summary():
    """Missing poll-summary returns None (not a mapping)."""

    record = normalize_detail({"id": "123"})
    assert record.numplayers_summary is None


def test_poll_summary_return_none_when_suggested_numplayers_missing():
    """When suggested_numplayers is absent, returns None."""

    raw = {
        "id": "123",
        "suggested_numplayers": None,
    }
    record = normalize_detail(raw)
    assert record.numplayers_summary is None


def test_poll_summary_only_bestwith():
    """When only bestwith is present, recommendedwith key is absent."""

    raw = {
        "id": "123",
        "suggested_numplayers": {
            "poll-summary": {
                "result": [
                    {"name": "bestwith", "value": "Best with 2 players"},
                ],
            },
        },
    }
    record = normalize_detail(raw)
    assert record.numplayers_summary == {"bestwith": "Best with 2 players"}


def test_poll_summary_only_recommendedwith():
    """When only recommendedwith is present, bestwith key is absent."""

    raw = {
        "id": "123",
        "suggested_numplayers": {
            "poll-summary": {
                "result": [
                    {"name": "recommmendedwith", "value": "Recommended with 4 players"},
                ],
            },
        },
    }
    record = normalize_detail(raw)
    assert record.numplayers_summary == {
        "recommendedwith": "Recommended with 4 players"
    }


def test_poll_summary_empty_result_returns_none():
    """Empty result array returns None (not empty mapping)."""

    raw = {
        "id": "123",
        "suggested_numplayers": {
            "poll-summary": {
                "result": [],
            },
        },
    }
    record = normalize_detail(raw)
    assert record.numplayers_summary is None


def test_poll_summary_ignores_unknown_names():
    """Unknown poll names are silently skipped, not treated as recommended."""

    raw = {
        "id": "123",
        "suggested_numplayers": {
            "poll-summary": {
                "result": [
                    {"name": "bestwith", "value": "Best with 3 players"},
                    {"name": "recommendedwith", "value": "Recommended with 5 players"},
                    {"name": "funwith", "value": "Fun with 2 players"},
                ],
            },
        },
    }
    record = normalize_detail(raw)
    assert record.numplayers_summary == {
        "bestwith": "Best with 3 players",
        "recommendedwith": "Recommended with 5 players",
    }
    assert "funwith" not in record.numplayers_summary
