"""Pure conversion of raw BGG responses into Jewel-owned records.

This module deliberately has no transport dependency.  The repository boundary
is responsible for obtaining raw responses; it passes their data here and only
the immutable records below may leave the BGG integration.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite

RawResponse = Mapping[str, object] | object


@dataclass(frozen=True)
class BGGLocalizedVersionRecord:
    """Localized title attached to one BGG edition/version."""

    version_id: int
    language: str | None
    title: str | None


@dataclass(frozen=True)
class BGGDetailRecord:
    """Canonical metadata returned by the BGG thing endpoint."""

    bgg_id: int
    name: str | None
    year: int | None
    min_players: int | None
    max_players: int | None
    playing_time: int | None
    min_playing_time: int | None
    max_playing_time: int | None
    designers: str | None
    publishers: str | None
    mechanics: str | None
    categories: str | None
    rating_bayes_average: float | None
    rating_average: float | None
    rating_median: float | None
    rating_stddev: float | None
    rating_num_weights: float | None
    bgg_rank: int | None
    boardgame_rank: int | None
    users_rated: int | None
    users_owned: int | None
    thumbnail: str | None
    image: str | None
    description: str | None
    item_type: str | None
    bgg_url: str | None
    plays_count: int | None
    expansions: tuple[int, ...] = ()
    expands: tuple[int, ...] = ()
    alternative_names: tuple[str, ...] = ()
    designers_list: tuple[str, ...] = ()
    publishers_list: tuple[str, ...] = ()
    mechanics_list: tuple[str, ...] = ()
    categories_list: tuple[str, ...] = ()
    families: tuple[str, ...] = ()
    localized_versions: tuple[BGGLocalizedVersionRecord, ...] = ()
    suggested_players: tuple[Mapping[str, object], ...] | None = None


@dataclass(frozen=True)
class BGGExpansionRelations:
    """Compact relationship data retained until collection-wide sync."""

    bgg_id: int
    expansions: tuple[int, ...]
    expands: tuple[int, ...]


@dataclass(frozen=True)
class BGGCollectionRecord:
    """A single configured-account collection observation."""

    bgg_id: int
    name: str | None
    rating: int | None
    numplays: int
    owned: bool
    prev_owned: bool
    wishlist: bool
    wishlist_priority: int | None
    want: bool
    want_to_play: bool
    want_to_buy: bool
    preordered: bool
    for_trade: bool
    comment: str | None
    last_modified: str | None
    min_players: int | None
    max_players: int | None
    playing_time: int | None
    min_playing_time: int | None
    max_playing_time: int | None
    year: int | None
    thumbnail: str | None
    image: str | None
    bgg_rank: int | None
    boardgame_rank: int | None
    rating_bayes_average: float | None
    rating_average: float | None
    rating_median: float | None
    rating_stddev: float | None
    users_rated: int | None
    quantity: int = 0
    version_id: int | None = None
    version_name: str | None = None
    version_language: str | None = None
    version_year: int | None = None
    version_publisher: str | None = None
    localized_title: str | None = None


@dataclass(frozen=True)
class BGGPlaySessionRecord:
    """One immutable play-session observation."""

    play_id: int | None
    played_on: str | None
    players: tuple[str, ...]


@dataclass(frozen=True)
class BGGPlaysRecord:
    """Aggregated plays data for a game."""

    bgg_id: int
    name: str | None
    plays_count: int
    play_sessions: tuple[BGGPlaySessionRecord, ...] = ()


@dataclass(frozen=True)
class BGGBatchRecord:
    """A lightweight search or batch result."""

    bgg_id: int
    name: str | None
    type: str | None
    year: int | None


def normalize_detail(raw: RawResponse) -> BGGDetailRecord:
    """Normalize one raw detail mapping without performing I/O."""

    stats = _value(raw, "stats")
    designers = _strings(_value(raw, "designers"))
    publishers = _strings(_value(raw, "publishers"))
    mechanics = _strings(_value(raw, "mechanics"))
    categories = _strings(_value(raw, "categories"))
    item_type = _text(_value(raw, "thing_type", "type"))
    if item_type is None:
        if _boolean(_value(raw, "expansion")):
            item_type = "boardgameexpansion"
        elif _boolean(_value(raw, "accessory")):
            item_type = "boardgameaccessory"
    return BGGDetailRecord(
        bgg_id=_required_id(raw),
        name=_text(_value(raw, "name")),
        year=_integer(_value(raw, "yearpublished", "year")),
        min_players=_integer(_value(raw, "minplayers", "min_players")),
        max_players=_integer(_value(raw, "maxplayers", "max_players")),
        playing_time=_integer(_value(raw, "playingtime", "playing_time")),
        min_playing_time=_integer(_value(raw, "minplaytime", "min_playing_time")),
        max_playing_time=_integer(_value(raw, "maxplaytime", "max_playing_time")),
        designers=_joined(designers),
        publishers=_joined(publishers),
        mechanics=_joined(mechanics),
        categories=_joined(categories),
        rating_bayes_average=_number(_stat(raw, stats, "rating_bayes_average")),
        rating_average=_number(_stat(raw, stats, "rating_average")),
        rating_median=_number(_stat(raw, stats, "rating_median")),
        rating_stddev=_number(_stat(raw, stats, "rating_stddev")),
        rating_num_weights=_number(_stat(raw, stats, "rating_num_weights")),
        bgg_rank=_integer(_stat(raw, stats, "bgg_rank")),
        boardgame_rank=_integer(_stat(raw, stats, "boardgame_rank")),
        users_rated=_integer(_stat(raw, stats, "users_rated")),
        users_owned=_integer(_value(raw, "users_owned")),
        thumbnail=_text(_value(raw, "thumbnail")),
        image=_text(_value(raw, "image")),
        description=_text(_value(raw, "description")),
        item_type=item_type,
        bgg_url=_text(_value(raw, "objecturl", "bgg_url")),
        plays_count=_integer(_value(raw, "plays_count")),
        expansions=_related_ids(_value(raw, "expansions")),
        expands=_related_ids(_value(raw, "expands")),
        alternative_names=_strings(_value(raw, "alternative_names")),
        designers_list=designers,
        publishers_list=publishers,
        mechanics_list=mechanics,
        categories_list=categories,
        families=_strings(_value(raw, "families")),
        localized_versions=_localized_versions(_value(raw, "localized_versions")),
        suggested_players=_suggested_players(_value(raw, "suggested_players")),
    )


def normalize_collection_item(raw: RawResponse) -> BGGCollectionRecord:
    """Normalize one raw collection mapping without performing I/O."""

    stats = _value(raw, "stats")
    version = _value(raw, "version")
    return BGGCollectionRecord(
        bgg_id=_required_id(raw),
        name=_text(_value(raw, "name")),
        rating=_integer(_value(raw, "rating")),
        numplays=_non_negative_integer(_value(raw, "numplays")),
        owned=_boolean(_value(raw, "owned")),
        prev_owned=_boolean(_value(raw, "prev_owned")),
        wishlist=_boolean(_value(raw, "wishlist")),
        wishlist_priority=_integer(_value(raw, "wishlist_priority")),
        want=_boolean(_value(raw, "want")),
        want_to_play=_boolean(_value(raw, "want_to_play")),
        want_to_buy=_boolean(_value(raw, "want_to_buy")),
        preordered=_boolean(_value(raw, "preordered")),
        for_trade=_boolean(_value(raw, "for_trade")),
        comment=_text(_value(raw, "comment")),
        last_modified=_text(_value(raw, "lastmodified", "last_modified")),
        min_players=_integer(_value(raw, "minplayers", "min_players")),
        max_players=_integer(_value(raw, "maxplayers", "max_players")),
        playing_time=_integer(_value(raw, "playingtime", "playing_time")),
        min_playing_time=_integer(_value(raw, "minplaytime", "min_playing_time")),
        max_playing_time=_integer(_value(raw, "maxplaytime", "max_playing_time")),
        year=_integer(_value(raw, "yearpublished", "year")),
        thumbnail=_text(_value(raw, "thumbnail")),
        image=_text(_value(raw, "image")),
        bgg_rank=_integer(_stat(raw, stats, "bgg_rank")),
        boardgame_rank=_integer(_stat(raw, stats, "boardgame_rank")),
        rating_bayes_average=_number(_stat(raw, stats, "rating_bayes_average")),
        rating_average=_number(_stat(raw, stats, "rating_average")),
        rating_median=_number(_stat(raw, stats, "rating_median")),
        rating_stddev=_number(_stat(raw, stats, "rating_stddev")),
        users_rated=_integer(_stat(raw, stats, "users_rated")),
        quantity=_non_negative_integer(_value(raw, "numowned", "quantity")),
        version_id=_integer(_value(version, "id")),
        version_name=_text(_value(version, "name")),
        version_language=_text(_value(version, "language")),
        version_year=_integer(_value(version, "year", "yearpublished")),
        version_publisher=_text(_value(version, "publisher")),
    )


def normalize_plays(
    raw: RawResponse,
    *,
    bgg_id: int,
    name: str | None = None,
) -> BGGPlaysRecord:
    """Normalize an aggregated plays response and its immutable sessions."""

    return BGGPlaysRecord(
        bgg_id=_required_positive_id(bgg_id),
        name=_text(name),
        plays_count=_non_negative_integer(_value(raw, "plays_count")),
        play_sessions=tuple(
            _normalize_play_session(session) for session in _items(_value(raw, "plays"))
        ),
    )


def normalize_batch_item(raw: RawResponse) -> BGGBatchRecord:
    """Normalize one raw batch or search result."""

    return BGGBatchRecord(
        bgg_id=_required_id(raw),
        name=_text(_value(raw, "name")),
        type=_text(_value(raw, "type")),
        year=_integer(_value(raw, "yearpublished", "year")),
    )


def _items(value: object | None) -> tuple[object, ...]:
    if not isinstance(value, Iterable) or isinstance(value, str | bytes | Mapping):
        return ()
    return tuple(value)


def _value(raw: RawResponse, field: str, *aliases: str) -> object | None:
    for name in (field, *aliases):
        value = raw.get(name) if isinstance(raw, Mapping) else getattr(raw, name, None)
        if value is None and not isinstance(raw, Mapping):
            data = getattr(raw, "_data", None)
            value = data.get(name) if isinstance(data, Mapping) else None
        if value is not None:
            return value
    return None


def _required_id(raw: RawResponse) -> int:
    value = _integer(_value(raw, "id", "bgg_id"))
    if value is None or value < 1:
        raise ValueError("BGG responses require a positive id")
    return value


def _required_positive_id(value: int) -> int:
    if value < 1:
        raise ValueError("BGG plays require a positive bgg_id")
    return value


def _stat(raw: RawResponse, stats: object | None, field: str) -> object | None:
    value = _value(stats, field) if stats is not None else None
    return value if value is not None else _value(raw, field)


def _integer(value: object | None) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _number(value: object | None) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).strip())
        return number if isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _boolean(value: object | None) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _strings(value: object | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = _text(value)
        return (text,) if text else ()
    if not isinstance(value, Iterable) or isinstance(value, bytes | Mapping):
        text = _text(value)
        return (text,) if text else ()
    return tuple(text for item in value if (text := _text(item)) is not None)


def _joined(values: tuple[str, ...]) -> str | None:
    return ", ".join(values) or None


def _non_negative_integer(value: object | None) -> int:
    integer = _integer(value)
    return integer if integer is not None and integer >= 0 else 0


def _related_ids(value: object | None) -> tuple[int, ...]:
    return tuple(
        related_id
        for item in _items(value)
        if (related_id := _integer(_value(item, "id", "bgg_id"))) is not None
        and related_id > 0
    )


def _localized_versions(value: object | None) -> tuple[BGGLocalizedVersionRecord, ...]:
    records = []
    for item in _items(value):
        version_id = _integer(_value(item, "id", "version_id"))
        if version_id is None or version_id < 1:
            continue
        records.append(
            BGGLocalizedVersionRecord(
                version_id=version_id,
                language=_text(_value(item, "language")),
                title=_text(_value(item, "canonical_name", "canonicalname", "title")),
            )
        )
    return tuple(records)


def _suggested_players(
    value: object | None,
) -> tuple[Mapping[str, object], ...] | None:
    """Extract structured player-count poll data from raw BGG response.

    Handles both the legacy list/player format and the actual BGG API
    results mapping::

        {
            "total_votes": N,
            "results": {
                "1": {"best_rating": 42, "recommended_rating": 10, ...},
                "7+": {"best_rating": 5, ...},
            },
        }

    Mapping ``*_rating`` keys to stable categories
    (``best``, ``recommended``, ``notrecommended``) and preserving
    player-count labels such as ``"7+"`` as-is.

    Returns ``None`` when the poll key is absent (partial fetch);
    returns an empty tuple when present but no valid entries found.
    """

    if value is None:
        return None

    if isinstance(value, Mapping):
        return _parse_results_mapping(value)

    return _parse_legacy_format(value)


def _parse_results_mapping(
    value: Mapping[str, object],
) -> tuple[Mapping[str, object], ...]:
    """Parse the actual BGG API results mapping."""

    results = value.get("results")
    if not isinstance(results, Mapping):
        return ()

    entries: list[dict[str, object]] = []
    for player_count, votes in results.items():
        if not isinstance(votes, Mapping):
            continue
        entry: dict[str, object] = {}
        # Preserve player-count label as string (e.g., '7+').
        entry["numplayers"] = str(player_count)
        for src, dest in (
            ("best_rating", "best"),
            ("recommended_rating", "recommended"),
            ("not_recommended_rating", "notrecommended"),
        ):
            cat_val = _integer(votes.get(src))
            if cat_val is not None:
                entry[dest] = cat_val
        if entry:
            entries.append(entry)
    return tuple(entries)


def _parse_legacy_format(
    value: object | None,
) -> tuple[Mapping[str, object], ...]:
    """Handle the legacy list/player format (deprecated but kept)."""

    def _poll_votes(node: object | None) -> dict[str, object] | None:
        if not isinstance(node, Mapping):
            return None
        numplayers = node.get("numplayers")
        categories: dict[str, object] = {}
        for category in ("best", "recommended", "notrecommended"):
            cat_val = _integer(node.get(category))
            if cat_val is not None:
                categories[category] = cat_val
        # Only return when numplayers is present and meaningful
        # (or categories carry data).
        if numplayers is None and not categories:
            return None
        result: dict[str, object] = {}
        if numplayers is not None:
            result["numplayers"] = numplayers
        result.update(categories)
        return result if result else None

    # Handle BGG API nesting: value may be {"suggested_players": ...} or
    # {"player": [...]} or the list directly.
    inner = _value(value, "suggested_players") if isinstance(value, Mapping) else value
    players = _value(inner, "player") if isinstance(inner, Mapping) else inner
    result = []
    for player_count in _items(players):
        poll = _poll_votes(player_count)
        if poll is not None:
            result.append(poll)
    return tuple(result)


def _normalize_play_session(raw: RawResponse) -> BGGPlaySessionRecord:
    players = _value(raw, "players")
    return BGGPlaySessionRecord(
        play_id=_integer(_value(raw, "id")),
        played_on=_text(_value(raw, "date")),
        players=_strings(players),
    )
