"""Canonical metadata upsert service.

Maps one normalised ``BGGDetailRecord`` into a canonical
``BGGMetadata`` row (upserted by ``bgg_id``). Expansion links are
synchronised in a separate authoritative collection pass.

This service:

* Creates or updates exactly one ``BGGMetadata`` row per
  distinct BGG ID.
* Maps all approved canonical fields from Packet 5,
  including item type, min/max playing time, ratings,
  ranks/counts, play aggregate, alternative names/families,
  and source URL fields.
* Updates source fields only when the record carries a
  non-``None`` value; ``None`` is treated as "omit" and
  leaves existing columns untouched.
* Synchronizes expansion links only after all canonical metadata for a
  complete collection is present, avoiding ordering dependencies.
* Never touches ``BoardGame`` local copies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import Q

from boardgames.bgg import BGGDetailRecord, BGGExpansionRelations
from boardgames.models import BGGExpansion, BGGMetadata

if TYPE_CHECKING:
    from collections.abc import Iterable


# ---------------------------------------------------------------------------
# Internal record used to carry back the updated metadata + links
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UpsertResult:
    """Return value of ``upsert_detail``."""

    metadata: BGGMetadata


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------


def _mapping_pairs(record: BGGDetailRecord) -> list[tuple[str, object]]:
    """Yield (column, value) pairs for columns that are not None.

    Every approved BGGDetailRecord field that has a corresponding
    BGGMetadata column is mapped here.  Fields that are None are
    silently skipped so that partial fetches preserve existing DB
    values (omit-semantics).
    """

    mappings: list[tuple[str, object]] = [
        ("name", record.name),
        ("yearpublished", record.year),
        ("minplayers", record.min_players),
        ("maxplayers", record.max_players),
        ("playingtime", record.playing_time),
        ("min_playing_time", record.min_playing_time),
        ("max_playing_time", record.max_playing_time),
        ("item_type", record.item_type),
        ("comment", record.description),
        ("bgg_url", record.bgg_url),
        ("thumbnail", record.thumbnail),
        ("image", record.image),
        ("publishers", record.publishers),
        ("designers", record.designers),
        ("mechanics", record.mechanics),
        ("categories", record.categories),
        ("alternative_names", _to_list(record.alternative_names)),
        ("families", _to_list(record.families)),
        ("rating_bayes_average", record.rating_bayes_average),
        ("rating_average", record.rating_average),
        ("rating_median", record.rating_median),
        ("rating_stddev", record.rating_stddev),
        ("rating_num_weights", record.rating_num_weights),
        ("bgg_rank", record.bgg_rank),
        ("boardgame_rank", record.boardgame_rank),
        ("users_rated", record.users_rated),
        ("users_owned", record.users_owned),
        ("plays_count", record.plays_count),
        ("suggested_players", record.suggested_players),
    ]

    return [(col, val) for col, val in mappings if val is not None]


def _to_list(value: tuple[str, ...] | str | None) -> list[str] | None:
    """Convert a tuple, string, or None to a list (or None)."""

    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    return list(value)


# ---------------------------------------------------------------------------
# Core service
# ---------------------------------------------------------------------------


def upsert_detail(record: BGGDetailRecord) -> UpsertResult:
    """Upsert one canonical BGG metadata row.

    Parameters
    ----------
    record :
        A normalised detail record returned by the BGG repository boundary.

    Returns
    -------
    UpsertResult
        The upserted ``BGGMetadata``. Expansion links are synchronized in a
        deliberate second pass by :func:`synchronize_expansion_links`.
    """

    mapping = _mapping_pairs(record)

    def _upsert_metadata() -> BGGMetadata:
        obj, _created = BGGMetadata.objects.update_or_create(
            bgg_id=record.bgg_id,
            defaults=dict(mapping) if mapping else {},
        )
        return obj

    with transaction.atomic():
        metadata = _upsert_metadata()

    return UpsertResult(metadata=metadata)


def synchronize_expansion_links(
    records: Iterable[BGGExpansionRelations],
    authoritative_ids: Iterable[int],
) -> list[BGGExpansion]:
    """Synchronize relationships from a complete authoritative collection.

    Both endpoints must occur in the collection and have canonical metadata.
    If a record references an absent endpoint, it is not authoritative for
    relationship removals from that source. A complete record with eligible
    endpoints replaces its owned links, so stale links are deleted only during
    a fully successful collection sync. ``expansions`` owns its parent-side
    links and ``expands`` owns its expansion-side links.
    """
    record_list = tuple(records)
    eligible_ids = set(authoritative_ids)
    records_by_id = {record.bgg_id: record for record in record_list}
    if set(records_by_id) != eligible_ids:
        return []

    metadata_by_id = BGGMetadata.objects.in_bulk(eligible_ids, field_name="bgg_id")
    if set(metadata_by_id) != eligible_ids:
        return []

    expected_pairs: set[tuple[int, int]] = set()
    parent_sources: set[int] = set()
    expansion_sources: set[int] = set()
    for record in record_list:
        expansion_ids = set(record.expansions) - {record.bgg_id}
        parent_ids = set(record.expands) - {record.bgg_id}
        if expansion_ids <= eligible_ids:
            parent_sources.add(record.bgg_id)
            expected_pairs.update(
                (expansion_id, record.bgg_id) for expansion_id in expansion_ids
            )
        if parent_ids <= eligible_ids:
            expansion_sources.add(record.bgg_id)
            expected_pairs.update(
                (record.bgg_id, parent_id) for parent_id in parent_ids
            )

    with transaction.atomic():
        parent_source_pks = [metadata_by_id[bgg_id].pk for bgg_id in parent_sources]
        expansion_source_pks = [
            metadata_by_id[bgg_id].pk for bgg_id in expansion_sources
        ]
        existing = BGGExpansion.objects.filter(
            Q(parent_id__in=parent_source_pks)
            | Q(expansion_id__in=expansion_source_pks)
        ).select_related("expansion", "parent")
        stale_ids = [
            link.pk
            for link in existing
            if (link.expansion.bgg_id, link.parent.bgg_id) not in expected_pairs
        ]
        if stale_ids:
            BGGExpansion.objects.filter(pk__in=stale_ids).delete()

        existing_pairs = {
            (link.expansion.bgg_id, link.parent.bgg_id)
            for link in BGGExpansion.objects.filter(
                expansion__bgg_id__in=eligible_ids,
                parent__bgg_id__in=eligible_ids,
            )
        }
        new_pairs = expected_pairs - existing_pairs
        BGGExpansion.objects.bulk_create(
            [
                BGGExpansion(
                    expansion=metadata_by_id[expansion_id],
                    parent=metadata_by_id[parent_id],
                )
                for expansion_id, parent_id in new_pairs
            ]
        )

    return list(
        BGGExpansion.objects.filter(
            expansion__bgg_id__in=eligible_ids,
            parent__bgg_id__in=eligible_ids,
        ).select_related("expansion", "parent")
    )


def upsert_many(
    records: Iterable[BGGDetailRecord],
) -> tuple[BGGMetadata, ...]:
    """Upsert a batch of records and return the created / updated rows.

    Each record is upserted in its own transaction so that a single
    failure does not corrupt the state of other records.
    """

    results: list[BGGMetadata] = []

    for record in records:
        result = upsert_detail(record)
        results.append(result.metadata)

    return tuple(results)
