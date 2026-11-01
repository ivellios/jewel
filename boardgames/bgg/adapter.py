"""BoardGameGeek adapter — normalises third-party objects into Jewel records."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

from boardgamegeek import BGGClient, BGGError

from .errors import (
    BGGAdapterError,
    BGGCredentialMissingError,
    BGGNetworkError,
    BGGNotFoundError,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Jewel-owned normalised records (immutable dataclasses)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BGGDetailRecord:
    """Normalised game detail fetched via ``/thing``."""

    bgg_id: int
    name: str | None
    year: int | None
    min_players: int | None
    max_players: int | None
    playing_time: int | None
    min_playing_time: int | None
    max_playing_time: int | None
    designers: str | None  # comma-separated or original text
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
    expansions: tuple[int, ...] = ()  # (id, ...) expansion IDs
    expands: tuple[int, ...] = ()  # (id, ...) IDs this game expands
    alternative_names: tuple[str, ...] = ()
    designers_list: tuple[str, ...] = ()
    publishers_list: tuple[str, ...] = ()
    mechanics_list: tuple[str, ...] = ()
    categories_list: tuple[str, ...] = ()
    families: tuple[str, ...] = ()


@dataclass(frozen=True)
class BGGRatingRecord:
    """Rating subset of a game or collection item."""

    bgg_id: int
    rating_bayes_average: float | None
    rating_average: float | None
    rating_median: float | None
    rating_stddev: float | None
    users_rated: int | None


@dataclass(frozen=True)
class BGGCollectionRecord:
    """Normalised collection item (user-level metadata + game data)."""

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
    # Game-level fields (subset)
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


@dataclass(frozen=True)
class BGGExpansionRecord:
    """One expansion or expanded-by relation."""

    id: int
    name: str


@dataclass(frozen=True)
class BGGPlaysRecord:
    """Aggregated plays data for a game."""

    bgg_id: int
    name: str | None
    plays_count: int
    play_sessions: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class BGGBatchRecord:
    """A lightweight item from a search or batch fetch."""

    bgg_id: int
    name: str | None
    type: str | None
    year: int | None


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class BGGAdapter:
    """High-level BGG adapter that owns its normalisation boundary.

    Public return values are Jewel-owned records / tuples.  Errors are
    deterministic and documented — no 500-level crashes from the library.
    """

    def __init__(
        self,
        access_token: str,
        api_url: str = "https://api.boardgamegeek.com",
        timeout: float = 30,
    ) -> None:
        if not access_token:
            raise BGGCredentialMissingError(
                "BGG access_token is required; "
                "set BGG_ACCESS_TOKEN before creating BGGAdapter."
            )

        self._client = BGGClient(
            access_token=access_token,
            timeout=timeout,
        )
        self._api_url = api_url
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Detail
    # ------------------------------------------------------------------

    def get_detail(self, bgg_id: int) -> BGGDetailRecord:
        """Fetch full detail for one game by BGG ID.

        Raises ``BGGNotFoundError`` when the game does not exist.
        Raises ``BGGNetworkError`` for API / network failures.
        """
        try:
            board_game = self._client.game(game_id=bgg_id)
        except BGGError as exc:
            self._handle_bgge_error(exc, bgg_id)

        return self._normalise_detail(bgg_id, board_game)

    # ------------------------------------------------------------------
    # Collection
    # ------------------------------------------------------------------

    def get_collection(
        self,
        user_name: str,
        ids: Iterable[int] | None = None,
        **filters: Any,
    ) -> tuple[BGGCollectionRecord, ...]:
        """Fetch collection entries for a user.

        When *ids* is given, fetches only those items; otherwise returns
        the full collection (filtered by *filters*).
        """
        try:
            collection = self._client.collection(
                user_name=user_name,
                ids=list(ids) if ids else None,
                **filters,
            )
        except BGGError as exc:
            self._handle_bgge_error(exc, user_name)

        return tuple(
            self._normalise_collection_item(item) for item in collection._items
        )

    # ------------------------------------------------------------------
    # Plays
    # ------------------------------------------------------------------

    def get_plays(
        self,
        bgg_id: int | None = None,
        name: str | None = None,
        min_date: date | None = None,
        max_date: date | None = None,
        subtype: str = "boardgame",
    ) -> BGGPlaysRecord:
        """Fetch aggregated play counts (and optional sessions)."""
        try:
            plays_obj = self._client.plays(
                name=name,
                game_id=bgg_id,
                min_date=min_date,
                max_date=max_date,
                subtype=subtype,
            )
        except BGGError as exc:
            self._handle_bgge_error(exc, bgg_id or name or "plays")

        sessions: tuple[dict[str, Any], ...] = tuple(
            {
                "id": s.id,
                "date": (
                    s.date.date().isoformat()
                    if hasattr(s, "date") and s.date is not None
                    else None
                ),
                "players": getattr(s, "players", []),
            }
            for s in plays_obj.plays
        )
        return BGGPlaysRecord(
            bgg_id=bgg_id or 0,
            name=name,
            plays_count=plays_obj.plays_count,
            play_sessions=sessions,
        )

    # ------------------------------------------------------------------
    # Expansions (derived from detail)
    # ------------------------------------------------------------------

    def get_expansions(self, bgg_id: int) -> tuple[BGGExpansionRecord, ...]:
        """Fetch expansion and expanded-by IDs for a game."""
        try:
            board_game = self._client.game(game_id=bgg_id)
        except BGGError as exc:
            self._handle_bgge_error(exc, bgg_id)

        expansion_ids: list[int] = [exp.id for exp in board_game._expansions]
        expands_ids: list[int] = [exp.id for exp in board_game._expands]

        records: list[BGGExpansionRecord] = []
        for eid in expansion_ids:
            try:
                bg = self._client.game(game_id=eid)
                records.append(BGGExpansionRecord(id=bg.id, name=bg.name))
            except BGGError:
                # If expansion fetch fails, store just the ID with placeholder
                records.append(BGGExpansionRecord(id=eid, name=""))

        for eid in expands_ids:
            try:
                bg = self._client.game(game_id=eid)
                records.append(BGGExpansionRecord(id=bg.id, name=bg.name))
            except BGGError:
                records.append(BGGExpansionRecord(id=eid, name=""))

        return tuple(records)

    # ------------------------------------------------------------------
    # Batch / Search
    # ------------------------------------------------------------------

    def get_batch(self, game_ids: Iterable[int]) -> tuple[BGGBatchRecord, ...]:
        """Fetch lightweight detail for multiple games at once."""
        ids = list(game_ids)
        if not ids:
            return ()

        try:
            board_games = self._client.game_list(ids)
        except BGGError as exc:
            self._handle_bgge_error(exc, game_ids)

        return tuple(self._normalise_batch(game) for game in board_games)

    def search(
        self,
        query: str,
        search_type: list[str] | None = None,
        exact: bool = False,
    ) -> tuple[BGGBatchRecord, ...]:
        """Search for games matching *query*."""
        try:
            results = self._client.search(query, search_type, exact)
        except BGGError as exc:
            self._handle_bgge_error(exc, query)

        return tuple(self._normalise_search_result(r) for r in results)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _handle_bgge_error(self, exc: BGGError, context: Any) -> None:
        """Map library exceptions to our own error hierarchy."""
        from boardgamegeek import (
            BGGApiError,
            BGGApiTimeoutError,
            BGGItemNotFoundError,
        )

        if isinstance(exc, BGGItemNotFoundError):
            raise BGGNotFoundError(f"BGG resource not found: {context}") from exc
        if isinstance(exc, BGGApiError | BGGApiTimeoutError):
            raise BGGNetworkError(f"Network / API error for {context}: {exc}") from exc
        raise BGGAdapterError(f"Unexpected BGG error for {context}: {exc}") from exc

    def _normalise_detail(self, bgg_id: int, board_game: Any) -> BGGDetailRecord:
        """Convert a third-party ``BoardGame`` into a ``BGGDetailRecord``."""

        # Designers / publishers / mechanics / categories: the library
        # exposes them as either lists or raw text depending on the API
        # endpoint and params.  Normalise to comma-separated strings.
        def _seq_to_str(field: Any) -> str | None:
            if field is None:
                return None
            if isinstance(field, list | tuple):
                joined = ", ".join(str(item) for item in field if item)
                # Empty list or all-empty items → None, not ""
                return joined or None
            return str(field)

        def _seq_to_tuple(field: Any) -> tuple[str, ...]:
            if field is None:
                return ()
            if isinstance(field, list | tuple):
                return tuple(str(item) for item in field if item)
            return (str(field),)

        # Rating fields live on ``_stats`` (BoardGameStats or plain dict).
        # The library stores them under ``_stats._data["..."]`` directly
        # (not as top-level attributes).  Fall back to the board_game attrs
        # (for compat) but prefer _stats when present.
        _stats = getattr(board_game, "_stats", None)

        def _rating(field: str) -> float | None:
            if _stats is not None and not isinstance(_stats, dict):
                inner = getattr(_stats, "_data", None)
                if inner is not None:
                    val = inner.get(field)
                    if val is not None:
                        return float(val)  # type: ignore[no-any-return]
            if isinstance(_stats, dict):
                val = _stats.get(field)
                if val is not None:
                    return float(val)  # type: ignore[no-any-return]
            return getattr(board_game, field, None)

        return BGGDetailRecord(
            bgg_id=bgg_id,
            name=board_game.name,
            year=board_game.year,
            min_players=board_game.min_players,
            max_players=board_game.max_players,
            playing_time=board_game.playing_time,
            min_playing_time=board_game.min_playing_time,
            max_playing_time=board_game.max_playing_time,
            designers=_seq_to_str(board_game.designers),
            publishers=_seq_to_str(board_game.publishers),
            mechanics=_seq_to_str(board_game.mechanics),
            categories=_seq_to_str(board_game.categories),
            rating_bayes_average=_rating("rating_bayes_average"),
            rating_average=_rating("rating_average"),
            rating_median=_rating("rating_median"),
            rating_stddev=_rating("rating_stddev"),
            rating_num_weights=_rating("rating_num_weights"),
            bgg_rank=int(_rating("bgg_rank")) if _rating("bgg_rank") is not None else None,  # type: ignore[arg-type]
            boardgame_rank=int(_rating("boardgame_rank")) if _rating("boardgame_rank") is not None else None,  # type: ignore[arg-type]
            users_rated=int(_rating("users_rated")) if _rating("users_rated") is not None else None,  # type: ignore[arg-type]
            users_owned=(
                getattr(board_game, "_data", {}).get("users_owned")
                if hasattr(board_game, "_data")
                else board_game.users_owned
            ),
            thumbnail=board_game.thumbnail,
            image=board_game.image,
            description=board_game.description,
            expansions=tuple(exp.id for exp in board_game._expansions),
            expands=tuple(exp.id for exp in board_game._expands),
            alternative_names=_seq_to_tuple(board_game.alternative_names),
            designers_list=_seq_to_tuple(board_game.designers),
            publishers_list=_seq_to_tuple(board_game.publishers),
            mechanics_list=_seq_to_tuple(board_game.mechanics),
            categories_list=_seq_to_tuple(board_game.categories),
            families=_seq_to_tuple(board_game.families),
        )

    def _normalise_collection_item(self, collection_game: Any) -> BGGCollectionRecord:
        """Convert a ``CollectionBoardGame`` into a ``BGGCollectionRecord``.

        The library stores boolean fields as int (0/1) and rating
        fields on ``_stats`` — normalise both.
        """

        # rating fields live on ``_stats`` when present
        _stats = getattr(collection_game, "_stats", None)

        def _rating(field: str) -> float | None:
            if _stats is not None and not isinstance(_stats, dict):
                inner = getattr(_stats, "_data", None)
                if inner is not None:
                    val = inner.get(field)
                    if val is not None:
                        return float(val)  # type: ignore[no-any-return]
            if isinstance(_stats, dict):
                val = _stats.get(field)
                if val is not None:
                    return float(val)  # type: ignore[no-any-return]
            return getattr(collection_game, field, None)

        def _bool_like(value: Any) -> bool:
            """Convert int 0/1 to bool (library returns int)."""
            if isinstance(value, int):
                return value != 0
            return bool(value)

        # Read boolean-like raw values from _data (the library's properties
        # normalize 1→False in some cases).  Read the numeric fields directly.
        _data: dict[str, Any] = getattr(collection_game, "_data", collection_game.__dict__)

        def _raw_owned() -> bool:
            val = int(_data.get("owned", 0))
            return val != 0

        def _raw_bool(field: str) -> bool:
            val = int(_data.get(field, 0))
            return val != 0

        # Numeric fields: library properties may return None; read from _data.
        def _raw_numeric(field: str) -> int | None:
            val = _data.get(field, None)
            if val is None:
                return None
            return int(val)

        return BGGCollectionRecord(
            bgg_id=collection_game.id,
            name=collection_game.name,
            rating=collection_game.rating,
            numplays=collection_game.numplays,
            owned=_raw_owned(),
            prev_owned=_raw_bool("prev_owned"),
            wishlist=_raw_bool("wishlist"),
            wishlist_priority=_raw_numeric("wishlist_priority"),
            want=_raw_bool("want"),
            want_to_play=_raw_bool("want_to_play"),
            want_to_buy=_raw_bool("want_to_buy"),
            preordered=_raw_bool("preordered"),
            for_trade=_raw_bool("for_trade"),
            comment=collection_game.comment,
            last_modified=collection_game.last_modified,
            min_players=collection_game.min_players,
            max_players=collection_game.max_players,
            playing_time=collection_game.playing_time,
            min_playing_time=collection_game.min_playing_time,
            max_playing_time=collection_game.max_playing_time,
            year=collection_game.year,
            thumbnail=collection_game.thumbnail,
            image=collection_game.image,
            bgg_rank=int(_rating("bgg_rank")) if _rating("bgg_rank") is not None else None,  # type: ignore[arg-type]
            boardgame_rank=int(_rating("boardgame_rank")) if _rating("boardgame_rank") is not None else None,  # type: ignore[arg-type]
            rating_bayes_average=_rating("rating_bayes_average"),
            rating_average=_rating("rating_average"),
            rating_median=_rating("rating_median"),
            rating_stddev=_rating("rating_stddev"),
            users_rated=int(_rating("users_rated")) if _rating("users_rated") is not None else None,  # type: ignore[arg-type]
        )

    def _normalise_batch(self, board_game: Any) -> BGGBatchRecord:
        """Convert a ``BoardGame`` from a batch/fetch into a batch record."""
        return BGGBatchRecord(
            bgg_id=board_game.id,
            name=board_game.name,
            type=None,
            year=board_game.year,
        )

    def _normalise_search_result(self, search_result: Any) -> BGGBatchRecord:
        """Convert a ``SearchResult`` into a batch record."""
        return BGGBatchRecord(
            bgg_id=search_result.id,
            name=search_result.name,
            type=search_result.type,
            year=search_result.year,
        )
