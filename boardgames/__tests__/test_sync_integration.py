"""Compact integration suite for the full BGG sync path.

Exercises repository → service → ORM boundaries with mocked BGG responses,
real Django test DB, and real orchestration/reconciliation/upsert services.

Scenarios covered:

1.  First import (full success).
2.  Repeated import (idempotent — new BGGSyncRun, updated BoardGame).
3.  Quantity observation without copy multiplication.
4.  Local name snapshot + local-only preservation.
5.  Expansion base rule / order (source-order independence).
6.  Complete removal + restoration.
7.  Partial detail-failure safety.
8.  Collection fetch failure (network error).
9.  Persisted diagnostics (counters + diagnostics JSON).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase

from boardgames.bgg import BGGCollectionRecord
from boardgames.bgg.errors import BGGNetworkError, BGGNotFoundError
from boardgames.models import (
    BGGCollectionObservation,
    BGGExpansion,
    BGGMetadata,
    BGGSyncRun,
    BGGSyncRunStatus,
    BoardGame,
)
from boardgames.services import full_reconcile
from boardgames.services.orchestration import OrchestrationResult

from .factories import (
    BGGMetadataFactory,
    collection_record,
)

# -----------------------------------------------------------------------
# Helpers — lean mocks at the repository boundary, no manual seeding.
# -----------------------------------------------------------------------


def _patch_upsert_detail() -> MagicMock:
    """Patch ``upsert_detail`` to create BGGMetadata rows."""

    from boardgames.models import BGGMetadata

    def _side_effect(record):
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
        side_effect=_side_effect,
    )


def _make_adapter(
    collection: tuple[BGGCollectionRecord, ...] = (),
    detail_records: tuple[dict, ...] | None = None,
    fail_collection: bool = False,
    fail_detail_ids: set[int] | None = None,
) -> MagicMock:
    """Build a mock BGGRepository with predictable behaviour."""

    from boardgames.bgg import BGGDetailRecord

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
    mock.get_details.side_effect = lambda bgg_ids: tuple(
        _get_detail_side_effect(bgg_id) for bgg_id in bgg_ids
    )
    return mock


def _run_with_upsert_patch(adapter: MagicMock, user_name: str) -> OrchestrationResult:
    """Call full_reconcile with upsert_detail patched to create BGGMetadata."""

    with _patch_upsert_detail():
        return full_reconcile(adapter, user_name)


# -----------------------------------------------------------------------
# 1. First import (full success) + quantity observation
# -----------------------------------------------------------------------


class FirstImportTest(TestCase):
    """Verify first-time import behaviour."""

    def test_creates_metadata_game_and_observations(self):
        """A fresh import creates BGGMetadata, BoardGame, and observations."""

        collection = (
            collection_record(bgg_id=910000, owned=True, quantity=2),
            collection_record(bgg_id=910001),
        )
        adapter = _make_adapter(collection)

        _run_with_upsert_patch(adapter, "importer")

        self.assertEqual(
            set(BGGMetadata.objects.values_list("bgg_id", flat=True)),
            {910000, 910001},
        )
        self.assertEqual(BoardGame.objects.filter(imported=True).count(), 2)
        # Quantity observation is persisted without multiplying copies.
        self.assertEqual(
            BGGMetadata.objects.get(bgg_id=910000).collection_observation.quantity,
            2,
        )

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
    """Verify that re-running creates new BGGSyncRun but updates copies."""

    def test_new_sync_run_each_run(self):
        """Repeated runs produce distinct BGGSyncRun records."""

        collection = (collection_record(bgg_id=910010),)
        adapter = _make_adapter(collection)

        _run_with_upsert_patch(adapter, "importer")
        _run_with_upsert_patch(adapter, "importer")

        self.assertEqual(BGGSyncRun.objects.count(), 2)

    def test_existing_game_updated(self):
        """Re-running with the same bgg_id updates imported_updated."""

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
# 3. Quantity observation without copy multiplication
# -----------------------------------------------------------------------


class QuantityNoDuplicationTest(TestCase):
    """Multiple collection entries with the same bgg_id → one BoardGame."""

    def test_same_bg_id_single_copy(self):
        """Two collection records with same bgg_id → one BoardGame."""

        collection = (
            collection_record(bgg_id=910040, owned=True),
            collection_record(bgg_id=910040, owned=True),
        )
        adapter = _make_adapter(collection)

        _run_with_upsert_patch(adapter, "importer")

        self.assertEqual(
            BoardGame.objects.filter(imported=True, metadata__bgg_id=910040).count(),
            1,
        )

    def test_last_non_owned_entry_does_not_create_a_local_copy(self):
        """The last collection observation determines ownership membership."""

        collection = (
            collection_record(bgg_id=910041, owned=True),
            collection_record(bgg_id=910041, owned=False),
        )
        adapter = _make_adapter(collection)

        _run_with_upsert_patch(adapter, "importer")

        game = BoardGame.objects.get(metadata__bgg_id=910041)
        self.assertTrue(game.removed)
        self.assertFalse(game.owned)
        observation = BGGCollectionObservation.objects.get(metadata__bgg_id=910041)
        self.assertFalse(observation.owned)


# -----------------------------------------------------------------------
# 4. Local name snapshot + local-only preservation
# -----------------------------------------------------------------------


class LocalPreservationTest(TestCase):
    """Verify local (imported=False) and local-override copies survive."""

    def test_local_only_game_unchanged(self):
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

    def test_local_fields_preserved_on_imported_copy(self):
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
# 5. Expansion base rule / order (source-order independence)
# -----------------------------------------------------------------------


class ExpansionIntegrationTest(TestCase):
    """Verify BGGExpansion rows created during integration."""

    def test_second_pass_creates_order_independent_links(self):
        """Source collection order is irrelevant after all details are present."""
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

    def test_base_before_expansion_creates_same_link(self):
        """Expanding from the base side: (expansion, parent) is deterministic."""
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

    def test_missing_base_not_linked(self):
        """An expansion cannot link to a base absent from the collection."""
        collection = (collection_record(bgg_id=910070),)
        adapter = _make_adapter(
            collection,
            ({"bgg_id": 910070, "name": "Expansion", "expands": (910071,)},),
        )

        full_reconcile(adapter, "importer")

        self.assertFalse(BGGExpansion.objects.exists())


# -----------------------------------------------------------------------
# 6. Complete removal + restoration
# -----------------------------------------------------------------------


class RemovalRestorationTest(TestCase):
    """Verify missing copies are soft-removed; reappearing restored."""

    def test_missing_copy_removed_by_empty_collection(self):
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

    def test_reappearing_copy_restored(self):
        """When a previously removed bgg_id reappears, it is restored."""

        meta = BGGMetadata.objects.create(bgg_id=910080, name="Returned Game")
        game = BoardGame.objects.create(
            metadata=meta, imported=True, owned=False, removed=True
        )

        collection = (collection_record(bgg_id=910080, owned=True),)
        adapter = _make_adapter(collection)

        _run_with_upsert_patch(adapter, "importer")

        refreshed = BoardGame.objects.get(pk=game.pk)
        self.assertFalse(refreshed.removed)
        self.assertTrue(refreshed.owned)


# -----------------------------------------------------------------------
# 7. Partial detail-failure safety
# -----------------------------------------------------------------------


class PartialFailureTest(TestCase):
    """Verify that partial detail-fetch failures are handled gracefully."""

    def test_failed_item_creates_no_anonymous_copy(self):
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
# 8. Collection fetch failure (network error)
# -----------------------------------------------------------------------


class FailedCollectionFetchTest(TestCase):
    """Verify that a failed collection fetch does not remove copies."""

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
# 9. Persisted diagnostics (counters + diagnostics JSON)
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
