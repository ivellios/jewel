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

        Only explicitly owned collection items create or update imported
        BoardGame rows. All collection statuses are still stored as
        observations. Imported rows no longer explicitly owned are soft-removed
        after a complete collection run.
    """

    bgg_to_record: dict[int, BGGCollectionRecord] = {}

    for record in collection:
        bgg_to_record[record.bgg_id] = record
    owned_ids = {bgg_id for bgg_id, record in bgg_to_record.items() if record.owned}

    with transaction.atomic():
        imported_copies = _find_target_copies(owned_ids, complete=complete)
        result = ReconciliationResult()

        for bgg_id, record in bgg_to_record.items():
            # Keep observations for all BGG collection statuses, but only
            # represent explicitly owned items as local collection copies.
            _upsert_observation(record, sync_run=sync_run)
            if not record.owned:
                continue

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

        # Handle removal when complete.
        if complete:
            for copy in imported_copies:
                if copy.metadata is None:
                    continue
                bgg_id = copy.metadata.bgg_id
                # Locally-owned (imported=False) copies are never selected.
                if bgg_id not in owned_ids and not copy.removed:
                    _soft_remove(copy)
                    result.removed.append(copy)

    return result


def remove_missing_imports(sync_run: BGGSyncRun) -> int:
    """Soft-remove imports not observed by this complete sync run.

    Collection observations are written as each item is processed, avoiding
    the need to retain the full collection in memory for the final comparison.
    Call only after every collection item was fetched and persisted.
    """

    with transaction.atomic():
        return (
            BoardGame.objects.filter(imported=True, removed=False)
            .exclude(
                metadata__collection_observation__sync_run=sync_run,
                metadata__collection_observation__owned=True,
            )
            .update(removed=True, owned=False)
        )


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
    update_fields = ["owned"]
    if record.version_id is not None:
        if record.version_language and not copy.language:
            copy.language = record.version_language
            update_fields.append("language")
        if record.version_name:
            if not copy.edition_label:
                copy.edition_label = record.version_name
                update_fields.append("edition_label")
            canonical_name = copy.metadata.name if copy.metadata is not None else None
            preferred_name = record.localized_title or canonical_name or record.name
            # Older sync code incorrectly used the BGG version label as the
            # game title. Repair that exact source-derived value while keeping
            # unrelated user-edited local names intact.
            if copy.name in {record.version_name, canonical_name} or not copy.name:
                copy.name = preferred_name
                update_fields.append("name")
    # Reappearing copies that were previously removed must be restored.
    if copy.removed:
        copy.removed = False
        copy.save(update_fields=[*update_fields, "removed"])
        return True

    copy.save(update_fields=update_fields)
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
        name=record.localized_title or metadata.name or record.name,
        language=record.version_language,
        edition_label=record.version_name,
        imported=True,
        owned=record.owned,
    )


def _soft_remove(copy: BoardGame) -> None:
    """Soft-remove an imported copy and clear its owned state."""

    copy.removed = True
    copy.owned = False
    copy.save(update_fields=["removed", "owned"])


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
