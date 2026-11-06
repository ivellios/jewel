"""Full-reconciliation orchestration service.

Chains the BGG repository / upsert / reconcile layer into a single
synchronous management command:

    BGG collection fetch → per-item detail + upsert → reconciliation → BGGSyncRun

Lifecycle semantics

* Only a fully successful collection fetch with every detail and canonical
  upsert succeeding authorises deletion of missing imported copies.
* A failing collection fetch (network / credential error) sets
  ``fetch_successful=False`` — missing imported copies are **never**
  removed.
* Per-item detail / upsert failures are recorded; successful items are
  reconciled without authorising removals.
* ``status`` is ``full`` when all items succeed, ``partial`` when some
  fail, and ``failed`` when the collection fetch itself fails (no
  items processed).
* The run is idempotent: repeated runs simply create new ``BGGSyncRun``
  records and update / create the same ``BoardGame`` / ``BGGMetadata``
  rows.

The service never schedules periodic tasks, never writes to BGG on
behalf of the user (reads only), and never touches play history.

One daily external scheduling / cron run is the operational assumption.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

from django.db import DatabaseError, transaction

from boardgames.bgg import (
    BGGCollectionRecord,
    BGGDetailRecord,
    BGGExpansionRelations,
    BGGRepositoryProtocol,
)
from boardgames.bgg.errors import (
    BGGAdapterError,
    BGGCredentialMissingError,
    BGGNetworkError,
    BGGNotFoundError,
)
from boardgames.models import (
    BGGSyncRun,
    BGGSyncRunStatus,
)
from boardgames.services.canonical_upsert import (
    synchronize_expansion_links,
    upsert_detail,
)
from boardgames.services.reconciliation import reconcile, remove_missing_imports

logger = logging.getLogger(__name__)

# Maximum number of per-item error messages to store (bounded diagnostics).
MAX_ERROR_MESSAGES = 50
# Maximum length per individual error message string.
MAX_ERROR_LENGTH = 500
# The installed boardgamegeek client supports at most 20 IDs per thing request.
DETAIL_BATCH_SIZE = 20

# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OrchestrationResult:
    """Return value of ``full_reconcile``."""

    bgg_sync_run: BGGSyncRun
    collection_count: int = 0
    items_fetched: int = 0
    items_failed: int = 0
    error_messages: list[str] = field(default_factory=list)
    imported_created: int = 0
    imported_updated: int = 0
    removed: int = 0
    restored: int = 0
    fetch_successful: bool = False


# ---------------------------------------------------------------------------
# Core service
# ---------------------------------------------------------------------------


def full_reconcile(
    repository: BGGRepositoryProtocol,
    user_name: str,
    progress_callback: Callable[[int, int], None] | None = None,
) -> OrchestrationResult:
    """Run the full reconciliation pipeline and persist diagnostics.

    Parameters
    ----------
    repository :
        A configured :class:`boardgames.bgg.BGGRepositoryProtocol` instance.
    user_name :
        The BGG user name whose collection to fetch.
    progress_callback :
        Optional callback receiving completed and total item counts while
        fetching details. Called once with ``(0, total)`` before processing.

    Returns
    -------
    OrchestrationResult
        Summary of all phases and the persisted ``BGGSyncRun`` record.
    """

    sync_run = BGGSyncRun.objects.create(
        status=BGGSyncRunStatus.FAILED,
        fetch_successful=False,
    )
    start_time = time.time()

    try:
        collection = repository.get_collection(user_name)
        fetch_successful = True
    except (BGGNetworkError, BGGCredentialMissingError) as exc:
        # Collection fetch failed — never authorise removal.
        _update_sync_run_error(
            sync_run,
            status=BGGSyncRunStatus.FAILED,
            fetch_successful=False,
            items_total=0,
            items_fetched=0,
            items_failed=0,
            error_messages=[str(exc)],
            diagnostics={
                "error": str(exc),
                "error_type": type(exc).__name__,
                "elapsed_seconds": round(time.time() - start_time, 3),
            },
            collection_count=0,
            imported_created=0,
            imported_updated=0,
            removed=0,
            restored=0,
        )
        return OrchestrationResult(
            bgg_sync_run=sync_run,
            collection_count=0,
            items_failed=0,
            error_messages=[str(exc)],
            fetch_successful=False,
        )
    except BGGAdapterError as exc:
        _update_sync_run_error(
            sync_run,
            status=BGGSyncRunStatus.FAILED,
            fetch_successful=False,
            items_total=0,
            items_fetched=0,
            items_failed=0,
            error_messages=[str(exc)],
            diagnostics={
                "error": str(exc),
                "error_type": type(exc).__name__,
                "elapsed_seconds": round(time.time() - start_time, 3),
            },
            collection_count=0,
            imported_created=0,
            imported_updated=0,
            removed=0,
            restored=0,
        )
        return OrchestrationResult(
            bgg_sync_run=sync_run,
            collection_count=0,
            items_failed=0,
            error_messages=[str(exc)],
            fetch_successful=False,
        )

    # Fetch succeeded.
    collection_count = len(collection)
    if progress_callback is not None:
        progress_callback(0, collection_count)

    expansion_records: list[BGGExpansionRelations] = []
    error_messages: list[str] = []
    detail_failed_count = 0
    items_fetched = 0
    imported_created = 0
    imported_updated = 0
    restored = 0

    collection_items = iter(enumerate(collection, start=1))

    def next_batch() -> list[tuple[int, BGGCollectionRecord]]:
        batch: list[tuple[int, BGGCollectionRecord]] = []
        for _ in range(DETAIL_BATCH_SIZE):
            item = next(collection_items, None)
            if item is None:
                break
            batch.append(item)
        return batch

    current_batch = next_batch()
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="bgg-detail") as executor:
        detail_future = (
            executor.submit(
                _fetch_detail_batch,
                repository,
                [record.bgg_id for _, record in current_batch],
            )
            if current_batch
            else None
        )

        while current_batch:
            try:
                assert detail_future is not None
                batch_results = detail_future.result()
            except (BGGNotFoundError, BGGNetworkError, BGGAdapterError) as exc:
                batch_results = {record.bgg_id: exc for _, record in current_batch}

            # Prefetch the next bounded batch while this batch is persisted.
            next_items = next_batch()
            detail_future = (
                executor.submit(
                    _fetch_detail_batch,
                    repository,
                    [record.bgg_id for _, record in next_items],
                )
                if next_items
                else None
            )

            for idx, col_record in current_batch:
                detail_result = batch_results.get(col_record.bgg_id)
                if isinstance(
                    detail_result,
                    BGGNotFoundError | BGGNetworkError | BGGAdapterError,
                ):
                    error_messages.append(
                        f"Item {idx}/{collection_count} (bgg_id={col_record.bgg_id}): "
                        f"{type(detail_result).__name__}: {detail_result}"
                    )
                    detail_failed_count += 1
                elif detail_result is None:
                    error_messages.append(
                        f"Item {idx}/{collection_count} (bgg_id={col_record.bgg_id}): "
                        "BGGAdapterError: detail missing from batch result"
                    )
                    detail_failed_count += 1
                else:
                    items_fetched += 1
                    try:
                        localized_title = next(
                            (
                                version.title
                                for version in detail_result.localized_versions
                                if version.version_id == col_record.version_id
                            ),
                            None,
                        )
                        col_record = replace(
                            col_record, localized_title=localized_title
                        )
                        upsert_detail(detail_result)
                        expansion_records.append(
                            BGGExpansionRelations(
                                bgg_id=detail_result.bgg_id,
                                expansions=detail_result.expansions,
                                expands=detail_result.expands,
                            )
                        )
                        item_result = reconcile(
                            (col_record,),
                            complete=False,
                            sync_run=sync_run,
                        )
                        imported_created += len(item_result.imported_created)
                        imported_updated += len(item_result.imported_updated)
                        restored += len(item_result.restored)
                    except (BGGAdapterError, DatabaseError) as exc:
                        error_messages.append(
                            f"Item {idx}/{collection_count} "
                            f"(bgg_id={col_record.bgg_id}): "
                            f"{type(exc).__name__}: {exc}"
                        )
                        detail_failed_count += 1

                if progress_callback is not None:
                    progress_callback(idx, collection_count)

            # Bounded error storage.
            if len(error_messages) > MAX_ERROR_MESSAGES:
                error_messages = error_messages[-MAX_ERROR_MESSAGES:]

            current_batch = next_items

    sync_run.items_total = collection_count

    # Relationship state is safe to reconcile only once every authoritative
    # detail was fetched and its canonical metadata was persisted.
    if fetch_successful and not detail_failed_count:
        synchronize_expansion_links(
            expansion_records,
            (col_record.bgg_id for col_record in collection),
        )
        removed = remove_missing_imports(sync_run)
    else:
        removed = 0

    # Any detail or canonical-persistence failure makes this input incomplete.
    sync_run.items_failed = detail_failed_count

    # Compute status.
    if sync_run.items_failed > 0:
        status = BGGSyncRunStatus.PARTIAL
    else:
        status = BGGSyncRunStatus.FULL

    elapsed_seconds = round(time.time() - start_time, 3)

    _update_sync_run_error(
        sync_run,
        status=status,
        fetch_successful=fetch_successful,
        items_total=collection_count,
        items_fetched=items_fetched,
        items_failed=sync_run.items_failed,
        error_messages=error_messages,
        diagnostics={
            "collection_count": collection_count,
            "detail_records": items_fetched,
            "authoritative": fetch_successful and not detail_failed_count,
            "imported_created": imported_created,
            "imported_updated": imported_updated,
            "removed": removed,
            "restored": restored,
            "fetch_successful": fetch_successful,
            "error_count": len(error_messages),
            "elapsed_seconds": elapsed_seconds,
        },
        collection_count=collection_count,
        imported_created=imported_created,
        imported_updated=imported_updated,
        removed=removed,
        restored=restored,
    )

    return OrchestrationResult(
        bgg_sync_run=sync_run,
        collection_count=collection_count,
        items_fetched=items_fetched,
        items_failed=sync_run.items_failed,
        error_messages=error_messages,
        imported_created=imported_created,
        imported_updated=imported_updated,
        removed=removed,
        restored=restored,
        fetch_successful=fetch_successful,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fetch_detail_batch(
    repository: BGGRepositoryProtocol,
    bgg_ids: list[int],
) -> dict[
    int,
    BGGDetailRecord | BGGNotFoundError | BGGNetworkError | BGGAdapterError,
]:
    """Fetch one batch, falling back to individual calls to isolate failures."""

    results: dict[
        int,
        BGGDetailRecord | BGGNotFoundError | BGGNetworkError | BGGAdapterError,
    ]
    try:
        records = repository.get_details(bgg_ids)
        results = {record.bgg_id: record for record in records}
        return results
    except (BGGNotFoundError, BGGNetworkError, BGGAdapterError):
        results = {}
        for bgg_id in bgg_ids:
            try:
                results[bgg_id] = repository.get_detail(bgg_id)
            except (BGGNotFoundError, BGGNetworkError, BGGAdapterError) as exc:
                results[bgg_id] = exc
        return results


def _update_sync_run_error(
    sync_run: BGGSyncRun,
    *,
    status: BGGSyncRunStatus,
    fetch_successful: bool,
    items_total: int,
    items_fetched: int,
    items_failed: int,
    error_messages: list[str],
    diagnostics: dict,
    collection_count: int,
    imported_created: int,
    imported_updated: int,
    removed: int,
    restored: int,
) -> None:
    """Persist a completed BGGSyncRun record."""

    # Bounded, user-friendly error text: join and truncate.
    bounded_messages = [msg[:MAX_ERROR_LENGTH] for msg in error_messages]
    error_text = "; ".join(bounded_messages) if bounded_messages else None

    with transaction.atomic():
        sync_run.status = status
        sync_run.fetch_successful = fetch_successful
        sync_run.items_total = items_total
        sync_run.items_fetched = items_fetched
        sync_run.items_failed = items_failed
        sync_run.error_messages = error_text
        sync_run.diagnostics = json.dumps(diagnostics, default=str)
        sync_run.completed_at = datetime.fromtimestamp(
            time.time(),
            tz=timezone.utc,  # noqa: UP017
        )
        sync_run.save(
            update_fields=[
                "status",
                "fetch_successful",
                "items_total",
                "items_fetched",
                "items_failed",
                "error_messages",
                "diagnostics",
                "completed_at",
            ]
        )
