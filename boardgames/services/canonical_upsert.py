"""Canonical metadata upsert service.

Maps one normalised ``BGGDetailRecord`` into a canonical
``BGGMetadata`` row (upserted by ``bgg_id``) and its
expansion / expands links via the existing ``BGGExpansion``
model.

This service:

* Creates or updates exactly one ``BGGMetadata`` row per
  distinct BGG ID.
* Updates source fields only when the record carries a
  non-``None`` value; ``None`` is treated as "omit" and
  leaves existing columns untouched.
* Writes ``BGGExpansion`` rows through ``get_or_create``
  so that duplicate calls are idempotent and self-links
  are silently skipped (enforced by the model's check
  constraint).
* Never touches ``BoardGame`` local copies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from django.db import transaction

from boardgames.bgg import BGGDetailRecord
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
    expansion_links: list[BGGExpansion] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------


def _mapping_pairs(record: BGGDetailRecord) -> list[tuple[str, object]]:
    """Yield (column, value) pairs for columns that are not None."""

    mappings: list[tuple[str, object]] = [
        ("name", record.name),
        ("yearpublished", record.year),
        ("minplayers", record.min_players),
        ("maxplayers", record.max_players),
        ("playingtime", record.playing_time),
        ("comment", record.description),
        ("thumbnail", record.thumbnail),
        ("image", record.image),
        ("publishers", record.publishers),
        ("designers", record.designers),
        ("mechanics", record.mechanics),
        ("categories", record.categories),
    ]

    return [(col, val) for col, val in mappings if val is not None]


# ---------------------------------------------------------------------------
# Core service
# ---------------------------------------------------------------------------


def upsert_detail(record: BGGDetailRecord) -> UpsertResult:
    """Upsert one canonical BGG metadata row + expansion links.

    Parameters
    ----------
    record :
        A normalised detail record produced by
        :class:`boardgames.bgg.BGGAdapter`.

    Returns
    -------
    UpsertResult
        The upserted ``BGGMetadata`` and any new
        ``BGGExpansion`` rows created during this call.
    """

    mapping = _mapping_pairs(record)
    created_ids: set[int] = set()

    def _upsert_metadata() -> tuple[BGGMetadata, bool]:
        obj, created = BGGMetadata.objects.update_or_create(
            bgg_id=record.bgg_id,
            defaults=dict(mapping) if mapping else {},
        )
        if created:
            created_ids.add(obj.bgg_id)
        return obj, created

    def _upsert_expansion_links() -> list[BGGExpansion]:
        """Create expansion and expands links, skipping self-links.

        Only links to expansion metadata that already exists in the
        database.  Links that already exist are returned only when
        they are newly created by this call, so repeated calls are
        idempotent.
        """

        new_links: list[BGGExpansion] = []

        for expansion_id in record.expansions:
            # Skip self-links before hitting the check constraint.
            if expansion_id == record.bgg_id:
                continue
            try:
                expansion_meta = BGGMetadata.objects.get(bgg_id=expansion_id)
            except BGGMetadata.DoesNotExist:
                continue
            base_meta = BGGMetadata.objects.get(bgg_id=record.bgg_id)
            link, created = BGGExpansion.objects.get_or_create(
                expansion=expansion_meta,
                parent=base_meta,
            )
            if created:
                new_links.append(link)

        for expands_id in record.expands:
            if expands_id == record.bgg_id:
                continue
            try:
                expands_meta = BGGMetadata.objects.get(bgg_id=expands_id)
            except BGGMetadata.DoesNotExist:
                continue
            base_meta = BGGMetadata.objects.get(bgg_id=record.bgg_id)
            link, created = BGGExpansion.objects.get_or_create(
                expansion=base_meta,
                parent=expands_meta,
            )
            if created:
                new_links.append(link)

        return new_links

    with transaction.atomic():
        metadata, created = _upsert_metadata()
        links = _upsert_expansion_links() if created else []

    return UpsertResult(
        metadata=metadata,
        expansion_links=links,
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
