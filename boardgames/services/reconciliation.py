"""Safe imported-copy reconciliation service.

Reconciles a normalised ``BGGCollectionRecord`` collection against
existing ``BoardGame`` local copies while preserving all local/manual
fields. Removal is authorized only when the caller explicitly declares
the input complete; in that case every imported copy is compared to the
authoritative collection, not merely the current batch.

This service:

* Finds or creates one imported ``BoardGame`` per distinct ``bgg_id``
  from the collection input — never duplicates on quantity.
* Preserves all local fields (name, language, edition_label,
  notes, review, played, play_priority, condition, storage,
  purchase_date).
* Soft-removes globally missing imported rows when ``complete=True``;
  never removes when incomplete.
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
from boardgames.models import (
    BGGCollectionObservation,
    BGGMetadata,
    BGGSyncRun,
    BoardGame,
)

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
    sync_run: BGGSyncRun | None = None,
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
        imported_copies = _find_target_copies(collected_ids, complete=complete)
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
                restored = _update_copy(matching, record)
                result.imported_updated.append(matching)
                if restored:
                    result.restored.append(matching)
            else:
                # New imported copies require canonical metadata. A failed
                # detail fetch without it is retried on the next sync rather
                # than creating an anonymous imported row.
                new_copy = _create_copy(record)
                if new_copy is not None:
                    result.imported_created.append(new_copy)

            _upsert_observation(record, sync_run=sync_run)

        # Handle removal when complete.
        if complete:
            for copy in imported_copies:
                if copy.metadata is None:
                    continue
                bgg_id = copy.metadata.bgg_id
                # Locally-owned (imported=False) copies are never selected.
                if bgg_id not in collected_ids and not copy.removed:
                    _soft_remove(copy)
                    result.removed.append(copy)

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_target_copies(
    collected_ids: set[int],
    *,
    complete: bool,
) -> list[BoardGame]:
    """Return imported copies relevant to this reconciliation.

    A complete collection is authoritative over every imported source row.
    Incomplete input may update only rows it actually contains.
    """

    copies = BoardGame.objects.filter(imported=True)
    if not complete:
        copies = copies.filter(metadata__bgg_id__in=collected_ids)
    return list(copies.select_related("metadata"))


def _update_copy(copy: BoardGame, record: BGGCollectionRecord) -> bool:
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
        return True

    copy.save(update_fields=["owned"])
    return False


def _create_copy(record: BGGCollectionRecord) -> BoardGame | None:
    """Create a new imported BoardGame copy linked to existing metadata.

    If the item's detail fetch failed and no ``BGGMetadata`` row exists,
    no row is created. Imported copies must retain their canonical source
    identity, so a later successful detail fetch can create one safely.
    """

    try:
        metadata = BGGMetadata.objects.get(bgg_id=record.bgg_id)
    except BGGMetadata.DoesNotExist:
        return None

    return BoardGame.objects.create(
        metadata=metadata,
        name=metadata.name,
        imported=True,
        owned=record.owned,
    )


def _soft_remove(copy: BoardGame) -> None:
    """Soft-remove an imported copy (set removed=True)."""

    copy.removed = True
    copy.save(update_fields=["removed"])


def _upsert_observation(
    record: BGGCollectionRecord,
    *,
    sync_run: BGGSyncRun | None,
) -> None:
    """Persist the one account-level collection observation for a game."""

    try:
        metadata = BGGMetadata.objects.get(bgg_id=record.bgg_id)
    except BGGMetadata.DoesNotExist:
        return

    BGGCollectionObservation.objects.update_or_create(
        metadata=metadata,
        defaults={
            "sync_run": sync_run,
            "quantity": record.quantity,
            "rating": record.rating,
            "numplays": record.numplays,
            "owned": record.owned,
            "prev_owned": record.prev_owned,
            "wishlist": record.wishlist,
            "wishlist_priority": record.wishlist_priority,
            "want": record.want,
            "want_to_play": record.want_to_play,
            "want_to_buy": record.want_to_buy,
            "preordered": record.preordered,
            "for_trade": record.for_trade,
            "comment": record.comment,
            "last_modified": record.last_modified,
        },
    )
