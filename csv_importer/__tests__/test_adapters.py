import datetime

import pytest

from csv_importer.adapters import CSVGameAdapter, CSVGameOnPlatformAdapter


@pytest.mark.parametrize(
    "input_value,output_value",
    [
        ("2+", 2),
        ("+3", 3),
        ("10", 10),
        ("2-4", 4),
        ("Bug", None),
        (None, None),
    ],
)
def test_max_players_string(input_value, output_value):
    # given
    adapter = CSVGameAdapter({"max_players": input_value})

    # when
    # then
    assert adapter.max_players == output_value


@pytest.mark.parametrize(
    "input_value,output_value",
    [
        ("10", 10),
        ("10+", 10),
        ("4-8", 8),
        ("5+", 5),
        ("Bug", None),
        (None, None),
        (True, None),
    ],
)
def test_review_values(input_value, output_value):
    # given
    adapter = CSVGameAdapter({"review": input_value})

    # when
    # then
    assert adapter.review == output_value


@pytest.mark.parametrize(
    "input_value,output_value",
    [
        ("", []),
        (None, []),
        ("Some", ["Some"]),
    ],
)
def test_genre_values(input_value, output_value):
    # given
    adapter = CSVGameAdapter({"genre": input_value})

    # when
    # then
    assert adapter.genres == output_value


@pytest.mark.parametrize(
    "input_value,output_value",
    [
        ("2022-05-02", datetime.datetime(2022, 5, 2)),
        (None, None),
        ("Some Bad Date", None),
    ],
)
def test_added_values(input_value, output_value):
    # given
    adapter = CSVGameOnPlatformAdapter({"added": input_value})

    # when
    # then
    assert adapter.added == output_value


@pytest.mark.parametrize(
    "input_value,output_value",
    [
        (True, True),
        (False, False),
        ("Some Bad Date", None),
        ("", None),
        ("4", True)
    ],
)
def test_controller_suppoer_values(input_value, output_value):
    # given
    adapter = CSVGameAdapter({"controller_support": input_value})

    # when
    # then
    assert adapter.controller_support == output_value


@pytest.mark.parametrize(
    "input_value,output_value",
    [
        ("10", 10),
        ("7", 7),
        ("5+", 5),
        ("", None),
        (None, None),
    ],
)
def test_play_priority_values(input_value, output_value):
    # given
    adapter = CSVGameAdapter({"play_priority": input_value})

    # when
    # then
    assert adapter.play_priority == output_value
