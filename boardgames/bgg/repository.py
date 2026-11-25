"""High-level BGG repository returning only Jewel-owned records."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from .adapter import (
    BGGBatchRecord,
    BGGCollectionRecord,
    BGGDetailRecord,
    BGGPlaysRecord,
    normalize_batch_item,
    normalize_collection_item,
    normalize_detail,
    normalize_plays,
)
from .client import DEFAULT_BGG_API_URL, BGGClient
from .errors import BGGAdapterError


@dataclass(frozen=True)
class BGGExpansionRecord:
    """A related expansion resolved through the repository boundary."""

    bgg_id: int
    name: str | None


class BGGRepositoryProtocol(Protocol):
    """BGG data required by synchronization services."""

    def get_collection(self, user_name: str) -> Sequence[BGGCollectionRecord]: ...

    def get_detail(self, bgg_id: int) -> BGGDetailRecord: ...

    def get_details(self, bgg_ids: Iterable[int]) -> tuple[BGGDetailRecord, ...]: ...


class BGGRepository:
    """Coordinate BGG transport and pure normalization for application code."""

    def __init__(
        self,
        access_token: str,
        api_url: str = DEFAULT_BGG_API_URL,
        timeout: float = 30,
    ) -> None:
        self._client = BGGClient(
            access_token=access_token,
            api_url=api_url,
            timeout=timeout,
        )

    def get_detail(self, bgg_id: int) -> BGGDetailRecord:
        return normalize_detail(self._client.game(bgg_id))

    def get_details(self, bgg_ids: Iterable[int]) -> tuple[BGGDetailRecord, ...]:
        ids = tuple(bgg_ids)
        if not ids:
            return ()
        if len(ids) > 20:
            raise ValueError("BGG detail batches cannot exceed 20 game IDs")
        records = tuple(
            normalize_detail(item) for item in _items(self._client.game_list(ids))
        )
        if {record.bgg_id for record in records} != set(ids):
            raise BGGAdapterError("BGG detail batch returned an unexpected set of IDs")
        return records

    def get_collection(
        self,
        user_name: str,
        ids: Iterable[int] | None = None,
        **filters: object,
    ) -> Sequence[BGGCollectionRecord]:
        filters.setdefault("version", True)
        game_ids = tuple(ids) if ids is not None else None
        records = [
            normalize_collection_item(item)
            for item in _items(
                self._client.collection(user_name, ids=game_ids, **filters)
            )
        ]

        # BGG may return a non-owned historical collection entry for a game
        # even when a separate owned copy exists. Fetch owned entries
        # explicitly so that the unfiltered result cannot mask that copy and
        # its selected version.
        if filters.get("own") is None:
            owned_filters = {**filters, "own": True}
            records.extend(
                normalize_collection_item(item)
                for item in _items(
                    self._client.collection(
                        user_name,
                        ids=game_ids,
                        **owned_filters,
                    )
                )
            )

        preferred_by_id: dict[tuple[int, int | None], BGGCollectionRecord] = {}
        for record in records:
            key = (record.bgg_id, record.collection_id)
            current = preferred_by_id.get(key)
            if current is None or _collection_record_priority(
                record
            ) > _collection_record_priority(current):
                preferred_by_id[key] = record
        return tuple(preferred_by_id.values())

    def get_plays(
        self,
        bgg_id: int,
        *,
        name: str | None = None,
        min_date: date | None = None,
        max_date: date | None = None,
        subtype: str = "boardgame",
    ) -> BGGPlaysRecord:
        return normalize_plays(
            self._client.plays(
                name=name,
                game_id=bgg_id,
                min_date=min_date,
                max_date=max_date,
                subtype=subtype,
            ),
            bgg_id=bgg_id,
            name=name,
        )

    def get_expansions(self, bgg_id: int) -> tuple[BGGExpansionRecord, ...]:
        detail = self.get_detail(bgg_id)
        records: list[BGGExpansionRecord] = []
        for related_id in (*detail.expansions, *detail.expands):
            try:
                related = self.get_detail(related_id)
            except BGGAdapterError:
                records.append(BGGExpansionRecord(bgg_id=related_id, name=None))
            else:
                records.append(
                    BGGExpansionRecord(bgg_id=related.bgg_id, name=related.name)
                )
        return tuple(records)

    def get_batch(self, game_ids: Iterable[int]) -> tuple[BGGBatchRecord, ...]:
        ids = tuple(game_ids)
        if not ids:
            return ()
        return tuple(
            normalize_batch_item(item) for item in _items(self._client.game_list(ids))
        )

    def search(
        self,
        query: str,
        search_type: list[str] | None = None,
        exact: bool = False,
    ) -> tuple[BGGBatchRecord, ...]:
        return tuple(
            normalize_batch_item(item)
            for item in _items(self._client.search(query, search_type, exact))
        )


def _items(raw_items: object) -> Sequence[object]:
    if not isinstance(raw_items, Iterable) or isinstance(raw_items, str | bytes | dict):
        raise BGGAdapterError("Unexpected BGG list response")
    if isinstance(raw_items, Sequence):
        return raw_items
    return tuple(raw_items)


def _collection_record_priority(record: BGGCollectionRecord) -> tuple[bool, bool, str]:
    """Prefer owned copies, selected versions, then the latest BGG record."""

    return (
        record.owned,
        record.version_id is not None,
        record.last_modified or "",
    )
