"""Django management command: sync_bgg_collection.

Orchestration entry-point that reads BGG credentials from Django settings,
builds a ``BGGAdapter``, and calls the full-reconciliation pipeline.

Exit codes
----------
* ``0`` — Full successful reconciliation (all items processed, no errors).
* ``1`` — Partial reconciliation (some items failed, but collection fetch
  itself succeeded).
* ``2`` — Failed reconciliation (collection fetch itself failed).

Settings
--------
The command reads the following from ``django.conf.settings``:

* ``BGG_ACCESS_TOKEN`` — BGG API access token (required).
* ``BGG_API_URL`` — BGG API base URL (default: ``https://api.boardgamegeek.com``).
* ``BGG_REQUEST_TIMEOUT`` — Request timeout in seconds (default: ``30``).
* ``BGG_USER_NAME`` — BGG user name whose collection to sync (required).

Scheduling assumption
---------------------
This command is designed for **one scheduled run per day** (e.g. a cron job
or system timer).  The BGG API imposes no rate limits for authenticated
requests, and the reconciliation is idempotent — repeated daily runs
simply create new ``BGGSyncRun`` records and update / create the same
``BoardGame`` / ``BGGMetadata`` rows without duplication.

The command never schedules periodic tasks, never writes to BGG on behalf
of the user (read-only), and never touches play history.

Usage
-----

.. code-block:: shell

    python manage.py sync_bgg_collection

Example output (full success):

.. code-block:: text

    Sync run: BGGSyncRun#42 (full)
    Collection: 123 items
    Fetched: 123 details
    Failed: 0
    Created: 5 imported copies
    Updated: 12 imported copies
    Removed: 2 removed copies
    Restored: 0 restored copies
    Fetch successful: True
    Elapsed: 12.345 s

Example output (partial failure):

.. code-block:: text

    Sync run: BGGSyncRun#43 (partial)
    Collection: 123 items
    Fetched: 120 details
    Failed: 3 items
    Created: 5 imported copies
    Updated: 11 imported copies
    Removed: 2 removed copies
    Restored: 0 restored copies
    Errors:
      - Item 45/123 (bgg_id=900123): BGGNotFoundError: Resource not found
      - Item 78/123 (bgg_id=900456): BGGNetworkError: Network / API error
    Fetch successful: True
    Elapsed: 15.678 s

Example output (failed):

.. code-block:: text

    Sync run: BGGSyncRun#44 (failed)
    Collection fetch failed: BGGCredentialMissingError: BGG access_token is required
    Fetch successful: False
    Elapsed: 0.123 s
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from boardgames.bgg.adapter import BGGAdapter
from boardgames.services import full_reconcile


class Command(BaseCommand):
    """Run full BGG collection reconciliation.

    Reads configuration from Django settings, orchestrates the full
    pipeline (collection fetch → detail fetch → canonical upsert →
    reconciliation), and persists diagnostics to ``BGGSyncRun``.

    Exit codes:
        0 — Full success (all items processed, no per-item errors).
        1 — Partial (some per-item errors, but collection fetch succeeded).
        2 — Failed (collection fetch itself failed).
    """

    help = (
        "Synchronises a user's BGG collection: fetches the full collection, "
        "fetches per-item detail, upserts canonical metadata, reconciles "
        "local copies, and records a BGGSyncRun with diagnostics."
    )

    def handle(self, *args, **options):
        """Execute the full reconciliation pipeline."""
        # Read settings (fail early with clear messages).
        access_token = getattr(settings, "BGG_ACCESS_TOKEN", None)
        api_url = getattr(settings, "BGG_API_URL", "https://api.boardgamegeek.com")
        request_timeout = getattr(settings, "BGG_REQUEST_TIMEOUT", 30)
        user_name = getattr(settings, "BGG_USER_NAME", None)

        # Validate required settings.
        missing = []
        if not access_token:
            missing.append("BGG_ACCESS_TOKEN")
        if not user_name:
            missing.append("BGG_USER_NAME")
        if missing:
            self.stderr.write(f"Error: Missing required settings: {', '.join(missing)}")
            raise SystemExit(2)

        # Build adapter and run full reconciliation.
        adapter = BGGAdapter(
            access_token=access_token,
            api_url=api_url,
            timeout=request_timeout,
        )

        result = full_reconcile(adapter, user_name)

        # Print diagnostics.
        self._print_result(result)

        # Exit code based on sync run status.
        status = result.bgg_sync_run.status
        if status == "full":
            raise SystemExit(0)
        if status == "partial":
            raise SystemExit(1)
        raise SystemExit(2)

    # ------------------------------------------------------------------
    # Diagnostics output
    # ------------------------------------------------------------------

    def _print_result(self, result) -> None:
        """Print reconciliation diagnostics to stdout/stderr."""
        sync_run = result.bgg_sync_run
        self.stdout.write(f"Sync run: {sync_run}")
        self.stdout.write(f"Collection: {result.collection_count} items")
        self.stdout.write(f"Fetched: {result.items_fetched} details")

        if result.items_failed > 0:
            self.stdout.write(f"Failed: {result.items_failed} items")

        self.stdout.write(f"Created: {result.imported_created} imported copies")
        self.stdout.write(f"Updated: {result.imported_updated} imported copies")
        self.stdout.write(f"Removed: {result.removed} removed copies")
        self.stdout.write(f"Restored: {result.restored} restored copies")

        if result.error_messages:
            self.stderr.write("Errors:")
            for msg in result.error_messages:
                self.stderr.write(f"  - {msg}")

        self.stdout.write(f"Fetch successful: {result.fetch_successful}")

        # Try to extract elapsed time from diagnostics.
        if sync_run.diagnostics:
            import json

            try:
                diag = json.loads(sync_run.diagnostics)
                elapsed = diag.get("elapsed_seconds")
                if elapsed is not None:
                    self.stdout.write(f"Elapsed: {elapsed} s")
            except (json.JSONDecodeError, AttributeError):
                pass
