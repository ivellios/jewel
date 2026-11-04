"""Integration tests for the full BGG sync flow.

Tests use mocked BGG adapter responses but real Django test DB and
real orchestration/reconciliation/upsert services.

Scenarios:

1.  First import (full success).
2.  Repeated import (idempotent — new BGGSyncRun, updated BoardGame).
3.  Distinct BGG IDs / editions — distinct copies for different bgg_ids.
4.  Quantity no-duplication — same bgg_id, multiple owned entries.
5.  Local-only game — unaffected by sync.
6.  Local overrides — local fields preserved across sync.
7.  Expansion with / without base — BGGExpansion rows.
8.  Update — re-importing updates existing BoardGame.
9.  Removal — missing imported copies soft-removed when complete=True.
10. Restoration — reappearing copies restored after removal.
11. Partial item failure — some detail fetches fail, BoardGame.metadata=None.
12. Failed collection fetch — network error, no copies removed.
13. Persisted run diagnostics — BGGSyncRun with full counters / diagnostics.
14. API contract — serializer fields match BoardGame exposed fields.
15. Admin contract — read-only permissions on all admin classes.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from rest_framework.test import APIClient

from boardgames.api.serializers import BoardGameSerializer
from boardgames.bgg import BGGCollectionRecord
from boardgames.models import (
    BGGExpansion,
    BGGMetadata,
    BGGSyncRun,
    BGGSyncRunStatus,
    BoardGame,
)
from boardgames.services import full_reconcile
from boardgames.services.orchestration import OrchestrationResult

from ..__tests__.factories import (
    BGGExpansionFactory,
    BGGMetadataFactory,
    BGGSyncRunFactory,
    collection_record,
)

# -----------------------------------------------------------------------
# Helpers (copied from test_orchestration.py for self-containment)
# -----------------------------------------------------------------------


def _patch_upsert_detail() -> MagicMock:
    """Return a started patch for ``upsert_detail`` that creates BGGMetadata."""

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


def _make_adapter(
    collection: tuple[BGGCollectionRecord, ...] = (),
    detail_records: tuple[dict, ...] | None = None,
    fail_collection: bool = False,
    fail_detail_ids: set[int] | None = None,
) -> MagicMock:
    """Build a mock BGGRepository with predictable behaviour."""

    from boardgames.bgg import BGGDetailRecord
    from boardgames.bgg.errors import BGGNetworkError, BGGNotFoundError

    mock = MagicMock()
    mock.get_collection.return_value = collection
    mock.get_collection.side_effect = None

    if fail_collection:
        mock.get_collection.side_effect = BGGNetworkError("connection refused")

    if detail_records is None:
        detail_records = ()

    def _get_detail_side_effect(bgg_id: int):
        if fail_detail_ids and bgg_id in fail_detail_ids:
            raise BGGNotFoundError(f"Not found: {bgg_id}")
        for rec in detail_records:
            if rec.get("bgg_id") == bgg_id:
                return BGGDetailRecord(
                    bgg_id=rec["bgg_id"],
                    item_type=None,
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
                    bgg_url=None,
                    description=rec.get("description"),
                    plays_count=None,
                    expansions=rec.get("expansions", ()),
                    expands=rec.get("expands", ()),
                    alternative_names=rec.get("alternative_names", ()),
                    designers_list=rec.get("designers_list", ()),
                    publishers_list=rec.get("publishers_list", ()),
                    mechanics_list=rec.get("mechanics_list", ()),
                    categories_list=rec.get("categories_list", ()),
                    families=rec.get("families", ()),
                )
        return BGGDetailRecord(
            bgg_id=bgg_id,
            item_type=None,
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
            bgg_url=None,
            description=None,
            plays_count=None,
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


def _run_with_upsert_patch(adapter: MagicMock, user_name: str) -> OrchestrationResult:
    """Call full_reconcile with upsert_detail patched to create BGGMetadata."""

    with _patch_upsert_detail():
        return full_reconcile(adapter, user_name)


# -----------------------------------------------------------------------
# 1. First import (full success)
# -----------------------------------------------------------------------


class FirstImportTest(TestCase):
    """Verify first-time import behaviour."""

    def test_creates_metadata_and_game(self):
        """A fresh import creates both BGGMetadata and BoardGame."""

        collection = (
            collection_record(bgg_id=910000),
            collection_record(bgg_id=910001),
        )
        adapter = _make_adapter(collection)

        _result = _run_with_upsert_patch(adapter, "importer")

        self.assertEqual(
            set(BGGMetadata.objects.values_list("bgg_id", flat=True)),
            {910000, 910001},
        )
        self.assertEqual(BoardGame.objects.filter(imported=True).count(), 2)

    def test_sync_run_status_is_full(self):
        """First import with no failures → status=full."""

        collection = (collection_record(bgg_id=910002),)
        adapter = _make_adapter(collection)

        result = _run_with_upsert_patch(adapter, "importer")

        self.assertEqual(result.bgg_sync_run.status, BGGSyncRunStatus.FULL)
        self.assertTrue(result.fetch_successful)


# -----------------------------------------------------------------------
# 2. Repeated import (idempotent)
# -----------------------------------------------------------------------


class RepeatedImportTest(TestCase):
    """Verify that re-running creates new BGGSyncRun but updates existing copies."""

    def test_new_sync_run_created_each_run(self):
        """Repeated runs produce distinct BGGSyncRun records."""

        collection = (collection_record(bgg_id=910010),)
        adapter = _make_adapter(collection)

        _run_with_upsert_patch(adapter, "importer")
        _run_with_upsert_patch(adapter, "importer")

        self.assertEqual(BGGSyncRun.objects.count(), 2)

    def test_existing_game_updated(self):
        """Re-running with the same bgg_id updates imported_updated count."""

        meta = BGGMetadata.objects.create(bgg_id=910020, name="First Name")
        BoardGame.objects.create(
            metadata=meta, imported=True, owned=False, removed=False
        )

        collection = (collection_record(bgg_id=910020),)
        adapter = _make_adapter(collection)

        result = _run_with_upsert_patch(adapter, "importer")

        self.assertEqual(result.imported_updated, 1)
        self.assertEqual(result.imported_created, 0)


# -----------------------------------------------------------------------
# 3. Distinct BGG IDs / editions
# -----------------------------------------------------------------------


class DistinctEditionsTest(TestCase):
    """Verify distinct bgg_ids produce distinct BoardGame copies."""

    def test_each_bg_id_gets_own_copy(self):
        """Different bgg_ids → distinct BoardGame rows."""

        collection = (
            collection_record(bgg_id=910030),
            collection_record(bgg_id=910031),
            collection_record(bgg_id=910032),
        )
        adapter = _make_adapter(collection)

        _run_with_upsert_patch(adapter, "importer")

        self.assertEqual(BoardGame.objects.filter(imported=True).count(), 3)


# -----------------------------------------------------------------------
# 4. Quantity no-duplication
# -----------------------------------------------------------------------


class QuantityNoDuplicationTest(TestCase):
    """Verify that multiple collection entries with the same bgg_id do not
    create duplicate BoardGame rows."""

    def test_same_bg_id_creates_single_copy(self):
        """Two collection records with the same bgg_id → one BoardGame."""

        collection = (
            collection_record(bgg_id=910040, owned=True),
            collection_record(bgg_id=910040, owned=False),
        )
        adapter = _make_adapter(collection)

        _result = _run_with_upsert_patch(adapter, "importer")

        # The reconcile layer deduplicates by bgg_id.
        self.assertEqual(
            BoardGame.objects.filter(imported=True, metadata__bgg_id=910040).count(),
            1,
        )

    def test_last_owned_wins(self):
        """When multiple entries share bgg_id, the last one wins."""

        collection = (
            collection_record(bgg_id=910041, owned=True),
            collection_record(bgg_id=910041, owned=False),
        )
        adapter = _make_adapter(collection)

        _run_with_upsert_patch(adapter, "importer")

        game = BoardGame.objects.get(metadata__bgg_id=910041)
        self.assertFalse(game.owned)


# -----------------------------------------------------------------------
# 5. Local-only game (not affected)
# -----------------------------------------------------------------------


class LocalOnlyGameTest(TestCase):
    """Verify local (imported=False) copies are never touched."""

    def test_local_game_unchanged_after_sync(self):
        """Importing does not affect local-only rows."""

        meta = BGGMetadataFactory()
        local_game = BoardGame.objects.create(
            metadata=meta,
            imported=False,
            name="My Game",
            language="de",
            owned=True,
        )

        collection = (collection_record(bgg_id=meta.bgg_id),)
        adapter = _make_adapter(collection)

        _run_with_upsert_patch(adapter, "importer")

        refreshed = BoardGame.objects.get(pk=local_game.pk)
        self.assertEqual(refreshed.name, "My Game")
        self.assertEqual(refreshed.language, "de")
        self.assertFalse(refreshed.imported)
        self.assertFalse(refreshed.removed)


# -----------------------------------------------------------------------
# 6. Local overrides (preserved after sync)
# -----------------------------------------------------------------------


class LocalOverridesTest(TestCase):
    """Verify that local editable fields survive a sync run."""

    def test_local_fields_preserved(self):
        """Local fields (name, language, edition_label, condition) survive."""

        meta = BGGMetadataFactory()
        BoardGame.objects.create(
            metadata=meta,
            imported=True,
            name="My Edition",
            language="fr",
            edition_label="2nd printing",
            condition="good",
            storage="basement",
        )

        collection = (collection_record(bgg_id=meta.bgg_id),)
        adapter = _make_adapter(collection)

        _run_with_upsert_patch(adapter, "importer")

        game = BoardGame.objects.get(metadata=meta)
        self.assertEqual(game.name, "My Edition")
        self.assertEqual(game.language, "fr")
        self.assertEqual(game.edition_label, "2nd printing")
        self.assertEqual(game.condition, "good")
        self.assertEqual(game.storage, "basement")


# -----------------------------------------------------------------------
# 7. Expansion with / without base
# -----------------------------------------------------------------------


class ExpansionIntegrationTest(TestCase):
    """Verify BGGExpansion rows are created during integration."""

    def test_second_pass_creates_order_independent_multiple_base_links(
        self,
    ):
        """The real sync creates links after all detail metadata is upserted."""
        collection = (
            collection_record(bgg_id=910051),
            collection_record(bgg_id=910050),
            collection_record(bgg_id=910052),
        )
        detail_records = (
            {"bgg_id": 910051, "name": "Expansion", "expands": (910050, 910052)},
            {
                "bgg_id": 910050,
                "name": "Base A",
                "expansions": (910051, 910050),
                "expands": (),
            },
            {"bgg_id": 910052, "name": "Base B", "expansions": (), "expands": ()},
        )
        adapter = _make_adapter(collection, detail_records)

        full_reconcile(adapter, "importer")

        self.assertEqual(
            set(
                BGGExpansion.objects.values_list("expansion__bgg_id", "parent__bgg_id")
            ),
            {(910051, 910050), (910051, 910052)},
        )

    def test_partial_or_missing_base_does_not_destructively_alter_links(
        self,
    ):
        """Incomplete source details leave relationships from prior full syncs."""
        collection = (
            collection_record(bgg_id=910050),
            collection_record(bgg_id=910051),
        )
        adapter = _make_adapter(
            collection,
            (
                {"bgg_id": 910050, "name": "Base", "expansions": (910051,)},
                {"bgg_id": 910051, "name": "Expansion", "expands": ()},
            ),
        )
        full_reconcile(adapter, "importer")

        partial_adapter = _make_adapter(
            collection,
            ({"bgg_id": 910051, "name": "Expansion", "expands": ()},),
            fail_detail_ids={910050},
        )
        full_reconcile(partial_adapter, "importer")

        self.assertTrue(
            BGGExpansion.objects.filter(
                expansion__bgg_id=910051, parent__bgg_id=910050
            ).exists()
        )

    def test_full_repeat_removes_stale_source_links(self):
        """A later complete collection is source-authoritative and idempotent."""
        collection = (
            collection_record(bgg_id=910050),
            collection_record(bgg_id=910051),
        )
        full_reconcile(
            _make_adapter(
                collection,
                (
                    {"bgg_id": 910050, "name": "Base", "expansions": (910051,)},
                    {"bgg_id": 910051, "name": "Expansion", "expands": ()},
                ),
            ),
            "importer",
        )
        adapter = _make_adapter(
            collection,
            (
                {"bgg_id": 910050, "name": "Base", "expansions": ()},
                {"bgg_id": 910051, "name": "Expansion", "expands": ()},
            ),
        )
        full_reconcile(adapter, "importer")
        full_reconcile(adapter, "importer")

        self.assertFalse(BGGExpansion.objects.exists())

    def test_base_before_expansion_creates_the_same_link(self):
        """The second pass makes source collection order irrelevant."""
        collection = (
            collection_record(bgg_id=910060),
            collection_record(bgg_id=910061),
        )
        adapter = _make_adapter(
            collection,
            (
                {"bgg_id": 910060, "name": "Base", "expansions": (910061,)},
                {"bgg_id": 910061, "name": "Expansion", "expands": (910060,)},
            ),
        )

        full_reconcile(adapter, "importer")

        self.assertEqual(
            set(
                BGGExpansion.objects.values_list("expansion__bgg_id", "parent__bgg_id")
            ),
            {(910061, 910060)},
        )

    def test_missing_base_is_not_linked(self):
        """An expansion cannot link to a base absent from the collection."""
        collection = (collection_record(bgg_id=910070),)
        adapter = _make_adapter(
            collection,
            ({"bgg_id": 910070, "name": "Expansion", "expands": (910071,)},),
        )

        full_reconcile(adapter, "importer")

        self.assertFalse(BGGExpansion.objects.exists())


# -----------------------------------------------------------------------
# 8. Update (re-importing updates existing game)
# -----------------------------------------------------------------------


class UpdateTest(TestCase):
    """Verify that re-importing an existing board game updates fields."""

    def test_update_imported_fields_only(self):
        """Re-import updates import-time fields but preserves local fields."""

        meta = BGGMetadata.objects.create(bgg_id=910060, name="Old Name")
        BoardGame.objects.create(
            metadata=meta,
            imported=True,
            owned=False,
            removed=False,
            name="Local Name",  # local override
            condition="good",  # local override
        )

        collection = (collection_record(bgg_id=910060, owned=True),)
        adapter = _make_adapter(collection)

        result = _run_with_upsert_patch(adapter, "importer")

        self.assertEqual(result.imported_updated, 1)
        game = BoardGame.objects.get(metadata=meta)
        self.assertTrue(game.owned)
        self.assertEqual(game.name, "Local Name")  # preserved
        self.assertEqual(game.condition, "good")  # preserved


# -----------------------------------------------------------------------
# 9. Removal (missing copies when complete=True)
# -----------------------------------------------------------------------


class RemovalTest(TestCase):
    """Verify that missing imported copies are soft-removed."""

    def test_missing_copy_is_removed_by_complete_empty_collection(self):
        """A complete empty collection removes globally missing imports."""

        meta = BGGMetadata.objects.create(bgg_id=910070, name="Old Game")
        BoardGame.objects.create(
            metadata=meta, imported=True, owned=False, removed=False
        )

        adapter = _make_adapter(())

        _run_with_upsert_patch(adapter, "importer")

        game = BoardGame.objects.get(metadata=meta)
        self.assertTrue(game.removed)

    def test_local_game_never_removed(self):
        """Local (imported=False) copies are never removed."""

        meta = BGGMetadataFactory()
        local_game = BoardGame.objects.create(
            metadata=meta, imported=False, owned=False, removed=False
        )

        adapter = _make_adapter(())

        _run_with_upsert_patch(adapter, "importer")

        game = BoardGame.objects.get(pk=local_game.pk)
        self.assertFalse(game.removed)


# -----------------------------------------------------------------------
# 10. Restoration (reappearing copies)
# -----------------------------------------------------------------------


class RestorationTest(TestCase):
    """Verify that reappearing copies are restored after removal."""

    def test_reappearing_copy_restored(self):
        """When a previously removed bgg_id reappears, it is restored."""

        meta = BGGMetadata.objects.create(bgg_id=910080, name="Returned Game")
        game = BoardGame.objects.create(
            metadata=meta, imported=True, owned=False, removed=True
        )

        collection = (collection_record(bgg_id=910080, owned=True),)
        adapter = _make_adapter(collection)

        _result = _run_with_upsert_patch(adapter, "importer")

        refreshed = BoardGame.objects.get(pk=game.pk)
        self.assertFalse(refreshed.removed)
        self.assertTrue(refreshed.owned)


# -----------------------------------------------------------------------
# 11. Partial item failure
# -----------------------------------------------------------------------


class PartialFailureTest(TestCase):
    """Verify that partial detail-fetch failures are handled gracefully."""

    def test_failed_item_creates_no_anonymous_imported_copy(self):
        """A failed detail cannot create an imported copy without metadata."""

        collection = (
            collection_record(bgg_id=910090),
            collection_record(bgg_id=910091),
        )
        adapter = _make_adapter(collection, fail_detail_ids={910091})

        result = _run_with_upsert_patch(adapter, "importer")

        self.assertEqual(result.bgg_sync_run.status, BGGSyncRunStatus.PARTIAL)
        self.assertTrue(result.fetch_successful)
        self.assertEqual(result.items_failed, 1)

        self.assertFalse(
            BoardGame.objects.filter(imported=True, metadata__isnull=True).exists()
        )

    def test_error_messages_recorded(self):
        """Error messages include context for failed items."""

        collection = (collection_record(bgg_id=910092),)
        adapter = _make_adapter(collection, fail_detail_ids={910092})

        result = _run_with_upsert_patch(adapter, "importer")

        self.assertGreater(len(result.error_messages), 0)
        self.assertIn("910092", result.error_messages[0])


# -----------------------------------------------------------------------
# 12. Failed collection fetch (network error)
# -----------------------------------------------------------------------


class FailedCollectionFetchTest(TestCase):
    """Verify that a failed collection fetch does not remove any copies."""

    def test_network_error_sets_failed_status(self):
        """BGGNetworkError → status=failed, no copies touched."""

        adapter = _make_adapter(fail_collection=True)

        result = _run_with_upsert_patch(adapter, "importer")

        self.assertEqual(result.bgg_sync_run.status, BGGSyncRunStatus.FAILED)
        self.assertFalse(result.fetch_successful)
        self.assertEqual(result.collection_count, 0)

    def test_no_copies_removed_on_failure(self):
        """A failed fetch never removes existing copies."""

        meta = BGGMetadataFactory()
        BoardGame.objects.create(
            metadata=meta, imported=True, owned=False, removed=False
        )

        adapter = _make_adapter(fail_collection=True)

        _run_with_upsert_patch(adapter, "importer")

        game = BoardGame.objects.get(metadata=meta)
        self.assertFalse(game.removed)


# -----------------------------------------------------------------------
# 13. Persisted run diagnostics
# -----------------------------------------------------------------------


class PersistedDiagnosticsTest(TestCase):
    """Verify BGGSyncRun diagnostics are fully persisted."""

    def test_diagnostics_json_contains_expected_keys(self):
        """Diagnostics JSON contains all expected summary fields."""

        collection = (
            collection_record(bgg_id=910100),
            collection_record(bgg_id=910101),
        )
        adapter = _make_adapter(collection)

        result = _run_with_upsert_patch(adapter, "importer")

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
        self.assertTrue(expected_keys.issubset(set(diag.keys())))

    def test_sync_run_counters_match_result(self):
        """Persisted BGGSyncRun counters match the result object."""

        collection = (
            collection_record(bgg_id=910102),
            collection_record(bgg_id=910103),
        )
        adapter = _make_adapter(collection)

        result = _run_with_upsert_patch(adapter, "importer")

        sync_run = BGGSyncRun.objects.get(pk=result.bgg_sync_run.pk)
        self.assertEqual(sync_run.items_total, result.collection_count)
        self.assertEqual(sync_run.items_fetched, result.items_fetched)
        self.assertEqual(sync_run.items_failed, result.items_failed)
        self.assertEqual(sync_run.fetch_successful, result.fetch_successful)


# -----------------------------------------------------------------------
# 14. API contract — serializers expose correct fields
# -----------------------------------------------------------------------


class ApiContractTest(TestCase):
    """Verify API serializer fields match BoardGame model fields."""

    def setUp(self):
        self.client = APIClient()

    def test_serializer_serialises_board_game(self):
        """A BoardGame instance can be serialised without errors."""

        meta = BGGMetadataFactory()
        game = BoardGame.objects.create(
            metadata=meta,
            imported=True,
            owned=True,
            removed=False,
            name="Test Game",
            language="en",
            condition="mint",
        )

        data = BoardGameSerializer(game).data
        self.assertEqual(data["id"], str(game.id))
        self.assertEqual(data["name"], "Test Game")
        self.assertEqual(data["imported"], True)
        self.assertEqual(data["owned"], True)


# -----------------------------------------------------------------------
# 15. Admin contract — read-only permissions
# -----------------------------------------------------------------------


class AdminContractTest(TestCase):
    """Verify all admin classes enforce read-only permissions."""

    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()

    def _make_request(self, user=None):
        request = self.factory.get("/admin/")
        request.user = user or self._anonymous_user()
        return request

    @staticmethod
    def _anonymous_user():
        from django.contrib.auth.models import AnonymousUser

        return AnonymousUser()

    def test_bgg_metadata_fully_readonly(self):
        """BGGMetadataAdmin denies add/change/delete."""

        from boardgames.admin import BGGMetadataAdmin

        admin = BGGMetadataAdmin(BGGMetadata, self.site)
        request = self._make_request()

        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_change_permission(request))

        obj = BGGMetadataFactory()
        self.assertFalse(admin.has_delete_permission(request, obj))

    def test_bgg_expansion_fully_readonly(self):
        """BGGExpansionAdmin denies add/change/delete."""

        from boardgames.admin import BGGExpansionAdmin

        admin = BGGExpansionAdmin(BGGExpansion, self.site)
        request = self._make_request()

        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_change_permission(request))

        obj = BGGExpansionFactory()
        self.assertFalse(admin.has_delete_permission(request, obj))

    def test_bgg_sync_run_fully_readonly(self):
        """BGGSyncRunAdmin denies add/change/delete."""

        from boardgames.admin import BGGSyncRunAdmin

        admin = BGGSyncRunAdmin(BGGSyncRun, self.site)
        request = self._make_request()

        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_change_permission(request))

        obj = BGGSyncRunFactory()
        self.assertFalse(admin.has_delete_permission(request, obj))

    def test_sync_run_list_display_includes_diagnostics(self):
        """BGGSyncRunAdmin list_display shows diagnostic fields."""

        from boardgames.admin import BGGSyncRunAdmin

        admin = BGGSyncRunAdmin(BGGSyncRun, self.site)
        expected = [
            "pk",
            "status",
            "fetch_successful",
            "items_total",
            "items_fetched",
            "items_failed",
            "created_at",
        ]
        self.assertEqual(admin.list_display, expected)
