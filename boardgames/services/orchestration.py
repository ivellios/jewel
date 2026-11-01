"""Full-reconciliation orchestration service.

Chains the existing adapter / upsert / reconcile layer into a single
synchronous management command:

    BGG collection fetch → per-item detail + upsert → reconciliation → BGGSyncRun

Lifecycle semantics

* A fully successful collection fetch (no network / credential error)
  sets ``fetch_successful=True`` and authorises deletion of missing
  imported copies (``complete=True`` passed to ``reconcile``).
* A failing collection fetch (network / credential error) sets
  ``fetch_successful=False`` — missing imported copies are **never**
  removed.
* Per-item detail / upsert failures are recorded; the run proceeds
  with whatever items succeeded.
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
from dataclasses import dataclass, field
from datetime import datetime, timezone

from django.db import transaction

from boardgames.bgg import BGGDetailRecord
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
from boardgames.services.canonical_upsert import upsert_detail
from boardgames.services.reconciliation import reconcile

logger = logging.getLogger(__name__)

# Maximum number of per-item error messages to store (bounded diagnostics).
MAX_ERROR_MESSAGES = 50
# Maximum length per individual error message string.
MAX_ERROR_LENGTH = 500

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
    adapter,  # BGGAdapter
    user_name: str,
) -> OrchestrationResult:
    """Run the full reconciliation pipeline and persist diagnostics.

    Parameters
    ----------
    adapter :
        A configured :class:`boardgames.bgg.BGGAdapter` instance.
    user_name :
        The BGG user name whose collection to fetch.

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
        collection = adapter.get_collection(user_name)
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
    detail_records: list[BGGDetailRecord] = []
    error_messages: list[str] = []

    for idx, col_record in enumerate(collection, start=1):
        try:
            detail = adapter.get_detail(col_record.bgg_id)
            detail_records.append(detail)
            sync_run.items_fetched = idx
        except (BGGNotFoundError, BGGNetworkError, BGGAdapterError) as exc:
            error_messages.append(
                f"Item {idx}/{collection_count} (bgg_id={col_record.bgg_id}): "
                f"{type(exc).__name__}: {exc}"
            )
            sync_run.items_failed = idx - len(detail_records)

        # Bounded error storage.
        if len(error_messages) > MAX_ERROR_MESSAGES:
            error_messages = error_messages[-MAX_ERROR_MESSAGES:]

    sync_run.items_total = collection_count
    sync_run.items_failed = len(error_messages)

    # Upsert canonical metadata for each successful detail.
    for detail in detail_records:
        try:
            upsert_detail(detail)
        except BGGAdapterError as exc:
            error_messages.append(
                f"Upsert bgg_id={detail.bgg_id}: {type(exc).__name__}: {exc}"
            )

    # Reconcile imported copies — only authorise removal when
    # fetch_successful=True (full collection fetch).
    result = reconcile(
        collection,
        complete=fetch_successful,
    )

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
        items_fetched=len(detail_records),
        items_failed=sync_run.items_failed,
        error_messages=error_messages,
        diagnostics={
            "collection_count": collection_count,
            "detail_records": len(detail_records),
            "imported_created": len(result.imported_created),
            "imported_updated": len(result.imported_updated),
            "removed": len(result.removed),
            "restored": len(result.restored),
            "fetch_successful": fetch_successful,
            "error_count": len(error_messages),
            "elapsed_seconds": elapsed_seconds,
        },
        collection_count=collection_count,
        imported_created=len(result.imported_created),
        imported_updated=len(result.imported_updated),
        removed=len(result.removed),
        restored=len(result.restored),
    )

    return OrchestrationResult(
        bgg_sync_run=sync_run,
        collection_count=collection_count,
        items_fetched=len(detail_records),
        items_failed=sync_run.items_failed,
        error_messages=error_messages,
        imported_created=len(result.imported_created),
        imported_updated=len(result.imported_updated),
        removed=len(result.removed),
        restored=len(result.restored),
        fetch_successful=fetch_successful,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
