"""Safe imported-copy reconciliation service.

Reconciles a normalised ``BGGCollectionRecord`` collection against
existing ``BoardGame`` local copies while preserving all local/manual
fields.  Only BGG-imported copies that appear within the current
collection batch are subject to reconciliation; copies outside the
batch remain untouched.  Removal is authorized only when the caller
explicitly declares the input complete.

This service:

* Finds or creates one imported ``BoardGame`` per distinct ``bgg_id``
  from the collection input — never duplicates on quantity.
* Preserves all local fields (name, language, edition_label,
  notes, review, played, play_priority, condition, storage,
  purchase_date).
* Soft-removes missing imported rows within the current collection
  batch when ``complete=True``; never removes when incomplete.
* Restores rows whose ``bgg_id`` reappears in a later run.
* Never touches local-only (``imported=False``) rows.
* Never writes to BGG, never performs hard deletes, never
  touches the network.

No Django ORM writes outside the ``BoardGame`` table.  Canonical
metadata upsert is handled separately by
:func:`boardgames.services.upsert_detail`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from django.db import transaction

from boardgames.bgg import BGGCollectionRecord
from boardgames.models import BGGMetadata, BoardGame

if TYPE_CHECKING:
    from collections.abc import Iterable

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReconciliationResult:
    """Return value of ``reconcile``."""

    imported_created: list[BoardGame] = field(default_factory=list)
    imported_updated: list[BoardGame] = field(default_factory=list)
    removed: list[BoardGame] = field(default_factory=list)
    restored: list[BoardGame] = field(default_factory=list)
    untouched_local: list[BoardGame] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core service
# ---------------------------------------------------------------------------


def reconcile(
    collection: Iterable[BGGCollectionRecord],
    *,
    complete: bool = True,
) -> ReconciliationResult:
    """Reconcile imported copies against a BGG collection.

    Parameters
    ----------
    collection :
        Normalised collection records from
        :class:`boardgames.bgg.BGGCollectionRecord`.  The caller is
        responsible for having run ``upsert_detail`` for canonical
        metadata before calling this function.
    complete :
        When ``True``, missing imported rows are soft-removed.
        When ``False``, no removal is authorized — missing
        imported rows are simply left as-is.

    Returns
    -------
    ReconciliationResult
        Categorised list of affected ``BoardGame`` instances.

    Notes
    -----
    Local-only (``imported=False``) rows are never touched
    regardless of ``complete``.  All local fields
    (name, language, edition_label, notes, review, played,
    play_priority, condition, storage, purchase_date) survive
    reconciliation unchanged.

    Only BoardGame rows whose ``metadata`` FK links to a
    BGGMetadata record matching the collection ``bgg_id``
    AND ``imported=True`` are subject to reconciliation.
    """

    collected_ids: set[int] = set()
    bgg_to_record: dict[int, BGGCollectionRecord] = {}

    for record in collection:
        collected_ids.add(record.bgg_id)
        bgg_to_record[record.bgg_id] = record

    with transaction.atomic():
        imported_copies = _find_target_copies(collected_ids)
        result = ReconciliationResult()

        for bgg_id, record in bgg_to_record.items():
            # Find the first matching copy (by bgg_id) among all imported copies.
            # Copies with metadata=None (failed detail fetch) are skipped here
            # — they can never match an existing copy because they have no
            # BGGMetadata FK to link against.
            matching = next(
                (
                    c
                    for c in imported_copies
                    if c.metadata and c.metadata.bgg_id == bgg_id
                ),
                None,
            )

            if matching:
                # Already imported — update ownership, keep local fields.
                _update_copy(matching, record)
                result.imported_updated.append(matching)
            else:
                # New imported copy — create with metadata link.
                new_copy = _create_copy(record)
                result.imported_created.append(new_copy)

        # Handle removal when complete.
        if complete:
            created_ids: set[int] = {
                c.metadata.bgg_id
                for c in result.imported_created
                if c.metadata is not None
            }

            for copy in imported_copies:
                if copy.metadata is None:
                    continue
                bgg_id = copy.metadata.bgg_id
                # Only remove if not newly created in this run and not in
                # the collection.  Locally-owned (imported=False) copies are
                # never removed regardless.
                if bgg_id not in collected_ids and bgg_id not in created_ids:
                    _soft_remove(copy)
                    result.removed.append(copy)

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_target_copies(
    collected_ids: set[int],
) -> list[BoardGame]:
    """Return imported copies whose metadata BGG IDs are in the batch.

    Only copies whose ``metadata__bgg_id`` appears in the current
    collection input are considered, so reconciliation touches no
    copies outside the batch.
    """

    return list(
        BoardGame.objects.filter(
            imported=True,
            metadata__bgg_id__in=collected_ids,
        ).select_related("metadata")
    )


def _update_copy(copy: BoardGame, record: BGGCollectionRecord) -> None:
    """Update an existing imported copy — preserve local fields."""

    # Update import-time fields from collection record.
    # All local fields (name, language, edition_label, notes, review,
    # played, play_priority, condition, storage, purchase_date) remain
    # untouched — they are preserved across reconciliation.
    copy.owned = record.owned
    # Reappearing copies that were previously removed must be restored.
    if copy.removed:
        copy.removed = False
        copy.save(update_fields=["owned", "removed"])
    else:
        copy.save(update_fields=["owned"])


def _create_copy(record: BGGCollectionRecord) -> BoardGame:
    """Create a new imported BoardGame copy linked to existing metadata.

    If the item's detail fetch failed and no ``BGGMetadata`` row exists,
    the ``metadata`` FK is left null — the column is intentionally
    nullable, so partial-failure reconciliation never crashes.
    """

    try:
        metadata = BGGMetadata.objects.get(bgg_id=record.bgg_id)
    except BGGMetadata.DoesNotExist:
        metadata = None

    return BoardGame.objects.create(
        metadata=metadata,
        imported=True,
        owned=record.owned,
    )


def _soft_remove(copy: BoardGame) -> None:
    """Soft-remove an imported copy (set removed=True)."""

    copy.removed = True
    copy.save(update_fields=["removed"])
