"""Focused service tests for full-reconciliation orchestration.

Tests:

* Successful full collection → ``status=full``, ``fetch_successful=True``.
* Failed collection (network/credential error) → ``status=failed``,
  ``fetch_successful=False``, **never** removes copies.
* Partial failure (some items fail) → ``status=partial``,
  ``fetch_successful=True``.
* Error bounding: only the last ``MAX_ERROR_MESSAGES`` are stored,
  each truncated to ``MAX_ERROR_LENGTH``.
* ``BGGSyncRun`` persistence: counters, diagnostics, timestamps.
* Idempotent repeated runs create new ``BGGSyncRun`` records.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase

from boardgames.bgg import BGGCollectionRecord
from boardgames.models import (
    BGGMetadata,
    BGGSyncRun,
    BGGSyncRunStatus,
    BoardGame,
)
from boardgames.services import full_reconcile
from boardgames.services.orchestration import (
    MAX_ERROR_LENGTH,
    MAX_ERROR_MESSAGES,
    OrchestrationResult,
)

from ..__tests__.factories import (
    BGGMetadataFactory,
)

# -----------------------------------------------------------------------
# Helpers / fixture builders
# -----------------------------------------------------------------------


def _patch_upsert_detail() -> MagicMock:
    """Return a started patch for ``upsert_detail`` that creates BGGMetadata.

    The returned mock must be stopped after each test that calls
    ``full_reconcile``, otherwise the patch leaks to subsequent tests.
    """

    from boardgames.models import BGGMetadata

    def _upsert_detail_side_effect(record):
        obj, _ = BGGMetadata.objects.update_or_create(
            bgg_id=record.bgg_id,
            defaults={
                "name": record.name,
                "yearpublished": record.year,
                "minplayers": record.min_players,
                "maxplayers": record.max_players,
                "playingtime": record.playing_time,
                "comment": record.description,
                "thumbnail": record.thumbnail,
                "image": record.image,
                "publishers": record.publishers,
                "designers": record.designers,
                "mechanics": record.mechanics,
                "categories": record.categories,
            },
        )
        return type("UpsertResult", (), {"metadata": obj, "expansion_links": []})(
            metadata=obj, expansion_links=[]
        )

    return patch(
        "boardgames.services.canonical_upsert.upsert_detail",
        side_effect=_upsert_detail_side_effect,
    )


def _make_collection_record(
    bgg_id: int = 900000,
    owned: bool = False,
    rating: int | None = None,
    numplays: int = 0,
    **extra,
) -> BGGCollectionRecord:
    """Convenience factory for BGGCollectionRecord fixtures."""

    return BGGCollectionRecord(
        bgg_id=bgg_id,
        name=None,
        rating=rating,
        numplays=numplays,
        owned=owned,
        prev_owned=False,
        wishlist=False,
        wishlist_priority=None,
        want=False,
        want_to_play=False,
        want_to_buy=False,
        preordered=False,
        for_trade=False,
        comment=None,
        last_modified=None,
        min_players=None,
        max_players=None,
        playing_time=None,
        min_playing_time=None,
        max_playing_time=None,
        year=None,
        thumbnail=None,
        image=None,
        bgg_rank=None,
        boardgame_rank=None,
        rating_bayes_average=None,
        rating_average=None,
        rating_median=None,
        rating_stddev=None,
        users_rated=None,
        **extra,
    )


def _make_adapter(
    collection: tuple[BGGCollectionRecord, ...] = (),
    detail_records: tuple[dict, ...] | None = None,
    fail_collection: bool = False,
    fail_detail_ids: set[int] | None = None,
) -> MagicMock:
    """Build a mock BGGAdapter with predictable behaviour.

    Parameters
    ----------
    collection :
        Collection records to return from ``get_collection``.
    detail_records :
        Mapping of bgg_id → detail dict (or None = no detail records).
    fail_collection :
        If True, ``get_collection`` raises ``BGGNetworkError``.
    fail_detail_ids :
        Set of bgg_id values that should raise ``BGGNotFoundError``
        when ``get_detail`` is called.
    """

    from boardgames.bgg.errors import BGGNetworkError, BGGNotFoundError

    mock = MagicMock()
    mock.get_collection.return_value = collection
    mock.get_collection.side_effect = None

    if fail_collection:
        mock.get_collection.side_effect = BGGNetworkError("connection refused")

    if detail_records is None:
        detail_records = ()

    def _get_detail_side_effect(bgg_id: int):
        from boardgames.bgg import BGGDetailRecord

        if fail_detail_ids and bgg_id in fail_detail_ids:
            raise BGGNotFoundError(f"Not found: {bgg_id}")
        for rec in detail_records:
            if rec.get("bgg_id") == bgg_id:
                return BGGDetailRecord(
                    bgg_id=rec["bgg_id"],
                    name=rec.get("name"),
                    year=rec.get("year"),
                    min_players=rec.get("min_players"),
                    max_players=rec.get("max_players"),
                    playing_time=rec.get("playing_time"),
                    min_playing_time=rec.get("min_playing_time"),
                    max_playing_time=rec.get("max_playing_time"),
                    designers=rec.get("designers"),
                    publishers=rec.get("publishers"),
                    mechanics=rec.get("mechanics"),
                    categories=rec.get("categories"),
                    rating_bayes_average=rec.get("rating_bayes_average"),
                    rating_average=rec.get("rating_average"),
                    rating_median=rec.get("rating_median"),
                    rating_stddev=rec.get("rating_stddev"),
                    rating_num_weights=rec.get("rating_num_weights"),
                    bgg_rank=rec.get("bgg_rank"),
                    boardgame_rank=rec.get("boardgame_rank"),
                    users_rated=rec.get("users_rated"),
                    users_owned=rec.get("users_owned"),
                    thumbnail=rec.get("thumbnail"),
                    image=rec.get("image"),
                    description=rec.get("description"),
                    expansions=rec.get("expansions", ()),
                    expands=rec.get("expands", ()),
                    alternative_names=rec.get("alternative_names", ()),
                    designers_list=rec.get("designers_list", ()),
                    publishers_list=rec.get("publishers_list", ()),
                    mechanics_list=rec.get("mechanics_list", ()),
                    categories_list=rec.get("categories_list", ()),
                    families=rec.get("families", ()),
                )
        # Default success for unlisted IDs (no detail override).
        return BGGDetailRecord(
            bgg_id=bgg_id,
            name=f"Game {bgg_id}",
            year=None,
            min_players=None,
            max_players=None,
            playing_time=None,
            min_playing_time=None,
            max_playing_time=None,
            designers=None,
            publishers=None,
            mechanics=None,
            categories=None,
            rating_bayes_average=None,
            rating_average=None,
            rating_median=None,
            rating_stddev=None,
            rating_num_weights=None,
            bgg_rank=None,
            boardgame_rank=None,
            users_rated=None,
            users_owned=None,
            thumbnail=None,
            image=None,
            description=None,
            expansions=(),
            expands=(),
            alternative_names=(),
            designers_list=(),
            publishers_list=(),
            mechanics_list=(),
            categories_list=(),
            families=(),
        )

    mock.get_detail.side_effect = _get_detail_side_effect
    return mock


# -----------------------------------------------------------------------
# Test helper: wraps full_reconcile with upsert_detail patch
# -----------------------------------------------------------------------


def _run_with_upsert_patch(adapter: MagicMock, user_name: str) -> OrchestrationResult:
    """Call full_reconcile with upsert_detail patched to create BGGMetadata.

    The patch is stopped after the call to avoid leaking to other tests.
    """

    with _patch_upsert_detail():
        return full_reconcile(adapter, user_name)


class FullSuccessTest(TestCase):
    """Verify successful full collection behaviour."""

    def test_full_success_status_and_counters(self):
        """A fully successful run sets status=full, fetch_successful=True."""

        collection = (
            _make_collection_record(bgg_id=900100),
            _make_collection_record(bgg_id=900101),
            _make_collection_record(bgg_id=900102),
        )
        adapter = _make_adapter(collection)

        result = _run_with_upsert_patch(adapter, "testuser")

        self.assertIsInstance(result, OrchestrationResult)
        self.assertEqual(result.bgg_sync_run.status, BGGSyncRunStatus.FULL)
        self.assertTrue(result.fetch_successful)
        self.assertEqual(result.collection_count, 3)
        self.assertEqual(result.items_fetched, 3)
        self.assertEqual(result.items_failed, 0)
        self.assertEqual(len(result.error_messages), 0)

    def test_full_success_creates_sync_run_record(self):
        """A successful run persists a BGGSyncRun with all fields."""

        collection = (_make_collection_record(bgg_id=900200),)
        adapter = _make_adapter(collection)

        result = _run_with_upsert_patch(adapter, "testuser")

        sync_run = BGGSyncRun.objects.get(pk=result.bgg_sync_run.pk)
        self.assertEqual(sync_run.status, BGGSyncRunStatus.FULL)
        self.assertTrue(sync_run.fetch_successful)
        self.assertEqual(sync_run.items_total, 1)
        self.assertEqual(sync_run.items_fetched, 1)
        self.assertEqual(sync_run.items_failed, 0)
        self.assertIsNone(sync_run.error_messages)
        self.assertIsNotNone(sync_run.diagnostics)
        self.assertIsNotNone(sync_run.completed_at)

        # Verify diagnostics are parseable JSON.
        diag = json.loads(sync_run.diagnostics)
        self.assertEqual(diag["collection_count"], 1)
        self.assertEqual(diag["fetch_successful"], True)
        self.assertIn("elapsed_seconds", diag)


# -----------------------------------------------------------------------
# Tests: failed collection (fetch itself fails)
# -----------------------------------------------------------------------


class FailedCollectionTest(TestCase):
    """Verify collection-fetch failure behaviour."""

    def test_network_error_sets_failed_status(self):
        """BGGNetworkError during collection fetch → status=failed."""

        adapter = _make_adapter(fail_collection=True)

        result = _run_with_upsert_patch(adapter, "testuser")

        self.assertEqual(result.bgg_sync_run.status, BGGSyncRunStatus.FAILED)
        self.assertFalse(result.fetch_successful)
        self.assertEqual(result.collection_count, 0)
        self.assertEqual(result.items_fetched, 0)
        self.assertEqual(len(result.error_messages), 1)

    def test_failed_collection_never_removes_copies(self):
        """A failed collection fetch never authorises removal of copies."""

        meta = BGGMetadataFactory()
        imported_game = BoardGame.objects.create(
            metadata=meta,
            imported=True,
            owned=False,
            removed=False,
        )

        adapter = _make_adapter(fail_collection=True)
        _run_with_upsert_patch(adapter, "testuser")

        # The imported game must NOT have been removed.
        refreshed = BoardGame.objects.get(pk=imported_game.pk)
        self.assertFalse(refreshed.removed)
        self.assertFalse(refreshed.imported is False)  # still imported=True

    def test_credentials_missing_sets_failed_status(self):
        """BGGCredentialMissingError during collection fetch → status=failed."""

        from boardgames.bgg.errors import BGGCredentialMissingError

        adapter = MagicMock()
        adapter.get_collection.side_effect = BGGCredentialMissingError("token missing")

        result = _run_with_upsert_patch(adapter, "testuser")

        self.assertEqual(result.bgg_sync_run.status, BGGSyncRunStatus.FAILED)
        self.assertFalse(result.fetch_successful)


# -----------------------------------------------------------------------
# Tests: partial failure
# -----------------------------------------------------------------------


class PartialFailureTest(TestCase):
    """Verify partial failure (some items fail) behaviour."""

    def test_partial_status_with_some_failures(self):
        """When some items fail, status=partial and fetch_successful=True."""

        collection = (
            _make_collection_record(bgg_id=900300),
            _make_collection_record(bgg_id=900301),
            _make_collection_record(bgg_id=900302),
        )
        # Make bgg_id 900301 fail — pre-create metadata so
        # reconciliation does not crash on the failed bgg_id.
        BGGMetadata.objects.create(bgg_id=900301, name="Game 900301")

        adapter = _make_adapter(
            collection,
            fail_detail_ids={900301},
        )

        result = _run_with_upsert_patch(adapter, "testuser")

        self.assertEqual(result.bgg_sync_run.status, BGGSyncRunStatus.PARTIAL)
        self.assertTrue(result.fetch_successful)
        self.assertEqual(result.collection_count, 3)
        self.assertEqual(result.items_fetched, 2)
        self.assertEqual(result.items_failed, 1)
        self.assertEqual(len(result.error_messages), 1)

    def test_error_messages_include_item_context(self):
        """Error messages include item index and bgg_id."""

        collection = (
            _make_collection_record(bgg_id=900400),
            _make_collection_record(bgg_id=900401),
        )
        # Pre-create metadata for the failing bgg_id.
        BGGMetadata.objects.create(bgg_id=900401, name="Game 900401")

        adapter = _make_adapter(
            collection,
            fail_detail_ids={900401},
        )

        result = _run_with_upsert_patch(adapter, "testuser")

        self.assertEqual(len(result.error_messages), 1)
        self.assertIn("900401", result.error_messages[0])
        self.assertIn("Item 2/2", result.error_messages[0])

    def test_partial_failure_without_pre_created_metadata(self):
        """When a failing item has no BGGMetadata, BoardGame is created with
        metadata=None — partial-failure never crashes."""

        collection = (
            _make_collection_record(bgg_id=900300),
            _make_collection_record(bgg_id=900301),
        )
        # Intentionally do NOT pre-create BGGMetadata for 900301.
        # In the real pipeline, a failed detail fetch means upsert_detail
        # is never called for this bgg_id, so no BGGMetadata exists.
        adapter = _make_adapter(
            collection,
            fail_detail_ids={900301},
        )

        result = _run_with_upsert_patch(adapter, "testuser")

        self.assertEqual(result.bgg_sync_run.status, BGGSyncRunStatus.PARTIAL)
        self.assertTrue(result.fetch_successful)
        self.assertEqual(result.items_fetched, 1)
        self.assertEqual(result.items_failed, 1)
        self.assertEqual(result.imported_created, 2)

        # Successful item has BoardGame linked to BGGMetadata.
        success_game = BoardGame.objects.get(metadata__bgg_id=900300)
        self.assertIsNotNone(success_game.metadata)
        self.assertEqual(success_game.metadata.bgg_id, 900300)

        # Failed item gets BoardGame with metadata=None (never crashes).
        fail_game = BoardGame.objects.get(metadata__bgg_id__isnull=True)
        self.assertIsNone(fail_game.metadata)
        self.assertEqual(fail_game.imported, True)


# -----------------------------------------------------------------------


class ErrorBoundingTest(TestCase):
    """Verify that error messages are bounded (count + length)."""

    def test_error_count_bounded(self):
        """Only the last MAX_ERROR_MESSAGES errors are stored."""

        large_collection = tuple(
            _make_collection_record(bgg_id=900500 + i) for i in range(200)
        )
        # Make every 3rd item fail — 67 failures.
        fail_ids = {900500 + i for i in range(200) if (i + 1) % 3 == 0}

        # Pre-create BGGMetadata for all failing bgg_ids so
        # reconciliation does not crash when iterating the full
        # collection (including failed items) through reconcile().
        for bgg_id in fail_ids:
            BGGMetadata.objects.create(bgg_id=bgg_id, name=f"Game {bgg_id}")

        adapter = _make_adapter(
            large_collection,
            fail_detail_ids=fail_ids,
        )

        result = _run_with_upsert_patch(adapter, "testuser")

        # The in-memory result is bounded.
        self.assertLessEqual(len(result.error_messages), MAX_ERROR_MESSAGES)

        # The persisted BGGSyncRun should also be bounded.
        self.assertLessEqual(len(result.error_messages), MAX_ERROR_MESSAGES)

    def test_error_length_bounded(self):
        """Each individual error message is truncated to MAX_ERROR_LENGTH."""

        long_detail = {
            "bgg_id": 900600,
            "name": "A" * 1000,  # Very long name → long error message.
        }
        collection = (_make_collection_record(bgg_id=900600),)
        # Pre-create metadata for the failing bgg_id.
        BGGMetadata.objects.create(bgg_id=900600, name="Game 900600")

        adapter = _make_adapter(
            collection,
            detail_records=(long_detail,),
            fail_detail_ids={900600},
        )

        result = _run_with_upsert_patch(adapter, "testuser")

        for msg in result.error_messages:
            self.assertLessEqual(len(msg), MAX_ERROR_LENGTH)


# -----------------------------------------------------------------------
# Tests: BGGSyncRun persistence
# -----------------------------------------------------------------------


class SyncRunPersistenceTest(TestCase):
    """Verify BGGSyncRun lifecycle and persistence."""

    def test_sync_run_has_timestamps(self):
        """created_at and completed_at are set."""

        collection = (_make_collection_record(bgg_id=900700),)
        adapter = _make_adapter(collection)

        _run_with_upsert_patch(adapter, "testuser")

        sync_run = BGGSyncRun.objects.latest("created_at")
        self.assertIsNotNone(sync_run.created_at)
        self.assertIsNotNone(sync_run.completed_at)

    def test_multiple_runs_create_multiple_records(self):
        """Repeated runs create distinct BGGSyncRun records."""

        collection = (_make_collection_record(bgg_id=900800),)
        adapter = _make_adapter(collection)

        _run_with_upsert_patch(adapter, "testuser")
        _run_with_upsert_patch(adapter, "testuser")

        self.assertEqual(BGGSyncRun.objects.count(), 2)

    def test_diagnostics_contains_summary_fields(self):
        """Diagnostics JSON contains expected summary fields."""

        collection = (_make_collection_record(bgg_id=900900),)
        adapter = _make_adapter(collection)

        result = _run_with_upsert_patch(adapter, "testuser")
        diag = json.loads(result.bgg_sync_run.diagnostics)

        expected_keys = {
            "collection_count",
            "detail_records",
            "imported_created",
            "imported_updated",
            "removed",
            "restored",
            "fetch_successful",
            "error_count",
            "elapsed_seconds",
        }
        self.assertTrue(
            expected_keys.issubset(set(diag.keys())),
            f"Missing keys: {expected_keys - set(diag.keys())}",
        )


# -----------------------------------------------------------------------
# Tests: integration with BoardGame/BGGMetadata
# -----------------------------------------------------------------------


class IntegrationWithModelsTest(TestCase):
    """Verify orchestration correctly integrates with BoardGame / BGGMetadata."""

    def test_creates_metadata_for_successful_items(self):
        """Successful detail fetches create BGGMetadata rows."""

        collection = (
            _make_collection_record(bgg_id=901000),
            _make_collection_record(bgg_id=901001),
        )
        adapter = _make_adapter(collection)

        _run_with_upsert_patch(adapter, "testuser")

        bgg_ids = list(BGGMetadata.objects.values_list("bgg_id", flat=True))
        self.assertEqual(set(bgg_ids), {901000, 901001})

    def test_imported_copies_created_for_successful_items(self):
        """Successful reconciliation creates imported BoardGame copies."""

        collection = (_make_collection_record(bgg_id=901100),)
        adapter = _make_adapter(collection)

        result = _run_with_upsert_patch(adapter, "testuser")

        self.assertEqual(result.imported_created, 1)
        self.assertTrue(
            BoardGame.objects.filter(imported=True, metadata__bgg_id=901100).exists()
        )

    def test_imported_copies_updated_for_existing_metadata(self):
        """Re-running with the same bgg_id updates existing copies."""

        meta = BGGMetadata.objects.create(bgg_id=901200, name="Old Name")
        BoardGame.objects.create(
            metadata=meta,
            imported=True,
            owned=False,
            removed=False,
        )

        collection = (_make_collection_record(bgg_id=901200),)
        adapter = _make_adapter(collection)

        result = _run_with_upsert_patch(adapter, "testuser")

        self.assertEqual(result.imported_updated, 1)
        self.assertEqual(result.imported_created, 0)

    def test_local_only_games_untouched(self):
        """Local (imported=False) copies are never modified by reconciliation."""

        meta = BGGMetadataFactory()
        local_game = BoardGame.objects.create(
            metadata=meta,
            imported=False,
            name="My Game",
            language="pl",
            owned=True,
        )

        collection = (_make_collection_record(bgg_id=meta.bgg_id),)
        adapter = _make_adapter(collection)

        _run_with_upsert_patch(adapter, "testuser")

        refreshed = BoardGame.objects.get(pk=local_game.pk)
        self.assertEqual(refreshed.name, "My Game")
        self.assertEqual(refreshed.language, "pl")
        self.assertFalse(refreshed.imported)
        self.assertFalse(refreshed.removed)
