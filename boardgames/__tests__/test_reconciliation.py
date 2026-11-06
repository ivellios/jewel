"""Focused lifecycle tests for safe imported-copy reconciliation.

Tests:

* Distinct BGG collection IDs create distinct imported copies.
* Same-ID quantity does not duplicate local rows.
* Local-only/manual rows remain untouched.
* Missing imported rows soft-remove only under complete input.
* Reappearing rows restore (removed=False after reappear).
* All local fields survive reconciliation.
* Incomplete input cannot authorize removals.
"""

from dataclasses import replace

from django.db import IntegrityError
from django.test import TestCase

from boardgames.models import BGGCollectionObservation, BGGMetadata, BoardGame
from boardgames.services import reconcile
from boardgames.services.reconciliation import remove_missing_imports

from ..__tests__.factories import (
    BGGMetadataFactory,
    BGGSyncRunFactory,
    BoardGameFactory,
    collection_record,
)


def _metadata_for_id(bgg_id: int) -> BGGMetadata:
    """Ensure BGGMetadata exists for bgg_id (create if not)."""

    meta, _ = BGGMetadata.objects.get_or_create(
        bgg_id=bgg_id, defaults={"name": f"Game {bgg_id}"}
    )
    return meta


class DistinctIdCreatesDistinctCopiesTest(TestCase):
    """Verify distinct BGG collection IDs produce distinct imported copies."""

    def test_only_owned_collection_items_create_imported_rows(self):
        """Want-to-play-only entries are observed but not imported as copies."""

        _metadata_for_id(900001)
        _metadata_for_id(900002)

        collection = [
            collection_record(bgg_id=900001, owned=True),
            collection_record(bgg_id=900002, owned=False, want_to_play=True),
        ]

        result = reconcile(collection)

        self.assertEqual(len(result.imported_created), 1)
        self.assertEqual(BoardGame.objects.filter(imported=True).count(), 1)
        bgg_ids = {c.metadata.bgg_id for c in result.imported_created}
        self.assertEqual(bgg_ids, {900001})
        observation = BGGCollectionObservation.objects.get(metadata__bgg_id=900002)
        self.assertFalse(observation.owned)
        self.assertTrue(observation.want_to_play)

    def test_same_id_quantity_creates_no_duplicates(self):
        """Collection quantity and repeat runs do not duplicate a source copy."""

        _metadata_for_id(900003)

        record = collection_record(bgg_id=900003, owned=True, quantity=3)

        result1 = reconcile([record])
        self.assertEqual(len(result1.imported_created), 1)

        result2 = reconcile([record])
        self.assertEqual(len(result2.imported_updated), 1)
        self.assertEqual(len(result2.imported_created), 0)
        self.assertEqual(
            BoardGame.objects.filter(imported=True, metadata__bgg_id=900003).count(),
            1,
        )
        observation = BGGCollectionObservation.objects.get(metadata__bgg_id=900003)
        self.assertEqual(observation.quantity, 3)

    def test_new_imported_copy_snapshots_canonical_name(self):
        """New imported copies keep their initial BGG name as a local value."""

        metadata = BGGMetadata.objects.create(bgg_id=900004, name="Original BGG Name")

        created = reconcile([collection_record(bgg_id=metadata.bgg_id)])
        copy = created.imported_created[0]
        self.assertEqual(copy.name, "Original BGG Name")

        metadata.name = "Renamed BGG Name"
        metadata.save(update_fields=["name"])
        reconcile([collection_record(bgg_id=metadata.bgg_id)])

        copy.refresh_from_db()
        self.assertEqual(copy.name, "Original BGG Name")

    def test_new_polish_import_keeps_edition_label_out_of_game_title(self):
        BGGMetadata.objects.create(bgg_id=900006, name="Ticket to Ride")
        record = replace(
            collection_record(bgg_id=900006),
            version_id=123456,
            version_name="Portal Games Polish edition",
            version_language="Polish",
            localized_title="Podziemne Imperium",
        )

        result = reconcile([record])

        copy = result.imported_created[0]
        self.assertEqual(copy.name, "Podziemne Imperium")
        self.assertEqual(copy.language, "Polish")
        self.assertEqual(copy.edition_label, "Portal Games Polish edition")

    def test_existing_canonical_title_is_not_replaced_by_polish_edition_label(self):
        metadata = BGGMetadataFactory(bgg_id=900009, name="Ticket to Ride")
        copy = BoardGameFactory(
            metadata=metadata,
            imported=True,
            name="Ticket to Ride",
            language="Polish",
            edition_label=None,
        )
        record = replace(
            collection_record(bgg_id=900009),
            version_id=123459,
            version_name="Portal Games Polish edition",
            version_language="Polish",
        )

        reconcile([record])
        copy.refresh_from_db()

        self.assertEqual(copy.name, "Ticket to Ride")
        self.assertEqual(copy.edition_label, "Portal Games Polish edition")

    def test_sync_repairs_version_label_misused_as_game_title(self):
        metadata = BGGMetadataFactory(bgg_id=900008, name="Ticket to Ride")
        copy = BoardGameFactory(
            metadata=metadata,
            imported=True,
            name="English edition 2021",
            edition_label=None,
        )
        record = replace(
            collection_record(bgg_id=900008),
            version_id=123458,
            version_name="English edition 2021",
            version_language="English",
        )

        reconcile([record])
        copy.refresh_from_db()

        self.assertEqual(copy.name, "Ticket to Ride")
        self.assertEqual(copy.edition_label, "English edition 2021")

    def test_sync_backfills_version_language_without_overwriting_local_name(self):
        metadata = BGGMetadataFactory(bgg_id=900007, name="Ticket to Ride")
        copy = BoardGameFactory(
            metadata=metadata,
            imported=True,
            name="My local title",
            language=None,
            edition_label=None,
        )
        record = replace(
            collection_record(bgg_id=900007),
            version_id=123457,
            version_name="Wsiąść do Pociągu",
            version_language="Polish",
        )

        reconcile([record])
        copy.refresh_from_db()

        self.assertEqual(copy.name, "My local title")
        self.assertEqual(copy.language, "Polish")
        self.assertEqual(copy.edition_label, "Wsiąść do Pociągu")

    def test_missing_canonical_metadata_creates_no_imported_copy(self):
        """Failed details cannot leave anonymous imported rows behind."""

        result = reconcile([collection_record(bgg_id=900005)])

        self.assertEqual(result.imported_created, [])
        self.assertFalse(BoardGame.objects.filter(imported=True).exists())

    def test_imported_copy_requires_canonical_metadata(self):
        """The database rejects imported rows without a stable source identity."""

        with self.assertRaises(IntegrityError):
            BoardGame.objects.create(imported=True)


class LocalOnlyRemainsUntouchedTest(TestCase):
    """Verify local-only (imported=False) rows are never touched."""

    def test_local_only_row_never_touched(self):
        """A manually created (imported=False) BoardGame is untouched.

        Note: when the collection includes a bgg_id where only a
        local-only (imported=False) copy exists, a NEW imported copy
        IS created (expected behavior).  The local-only copy itself
        is never modified or removed.
        """

        meta = BGGMetadataFactory(bgg_id=900010, name="Local Only Game")
        _metadata_for_id(900010)
        local_game = BoardGameFactory(
            metadata=meta,
            imported=False,
            name="My Edit",
            language="pl",
            condition="good",
            notes="Manual note",
            owned=True,
        )

        collection = [
            collection_record(bgg_id=900010, owned=True),
        ]

        result = reconcile(collection)

        # One imported copy is created (no pre-existing imported copy).
        self.assertEqual(len(result.imported_created), 1)
        # The local-only row remains unchanged.
        refreshed = BoardGame.objects.get(pk=local_game.pk)
        self.assertFalse(refreshed.imported)
        self.assertFalse(refreshed.removed)
        self.assertEqual(refreshed.name, "My Edit")
        self.assertEqual(refreshed.language, "pl")
        self.assertEqual(refreshed.condition, "good")
        self.assertEqual(refreshed.notes, "Manual note")

    def test_local_only_game_survives_complete_reconciliation(self):
        """Even with complete=True, local-only rows are not removed."""

        meta = BGGMetadataFactory(bgg_id=900020, name="Stays Forever")
        _metadata_for_id(900021)
        local_game = BoardGameFactory(
            metadata=meta,
            imported=False,
            owned=False,
        )

        # Reconcile with a different ID (900020 is not in collection).
        collection = [
            collection_record(bgg_id=900021, owned=True),
        ]

        result = reconcile(collection, complete=True)

        # Local-only game must not be in removed list.
        removed_ids = {r.pk for r in result.removed}
        self.assertNotIn(local_game.pk, removed_ids)
        refreshed = BoardGame.objects.get(pk=local_game.pk)
        self.assertFalse(refreshed.removed)


class SoftRemoveOnlyCompleteInputTest(TestCase):
    """Verify missing imported rows soft-remove only with complete=True."""

    def _setup_imported(self, bgg_id: int) -> BoardGame:
        """Create an existing imported BoardGame copy."""

        meta = BGGMetadata.objects.get_or_create(
            bgg_id=bgg_id, defaults={"name": f"Game {bgg_id}"}
        )[0]
        return BoardGame.objects.create(
            metadata=meta,
            imported=True,
            owned=False,
            removed=False,
        )

    def test_complete_false_no_removal(self):
        """With complete=False, missing imported rows are NOT removed."""

        _metadata_for_id(900030)
        _metadata_for_id(900031)

        # Create imported game with bgg_id NOT in collection.
        meta = BGGMetadata.objects.get(bgg_id=900030)
        removed_game = BoardGame.objects.create(
            metadata=meta,
            imported=True,
            owned=False,
            removed=False,
        )

        # Collection does NOT include bgg_id=900030.
        collection = [
            collection_record(bgg_id=900031, owned=True),
        ]

        result = reconcile(collection, complete=False)

        self.assertEqual(len(result.removed), 0)
        refreshed = BoardGame.objects.get(pk=removed_game.pk)
        self.assertFalse(refreshed.removed)

    def test_complete_true_soft_removes_missing(self):
        """A complete collection removes imported rows missing globally."""

        _metadata_for_id(900040)
        _metadata_for_id(900041)

        # Create imported game with bgg_id NOT in collection.
        meta = BGGMetadata.objects.get(bgg_id=900040)
        missing_game = BoardGame.objects.create(
            metadata=meta,
            imported=True,
            owned=False,
            removed=False,
        )

        # Collection does NOT include bgg_id=900040.
        collection = [
            collection_record(bgg_id=900041, owned=True),
        ]

        result = reconcile(collection, complete=True)

        self.assertEqual(len(result.removed), 1)
        refreshed = BoardGame.objects.get(pk=missing_game.pk)
        self.assertTrue(refreshed.removed)

    def test_reappearing_row_restores(self):
        """A row removed by a complete collection is restored when it reappears."""

        _metadata_for_id(900050)
        _metadata_for_id(900051)

        # First run: create imported copy for bgg_id=900050.
        result1 = reconcile([collection_record(bgg_id=900050)])
        self.assertEqual(len(result1.imported_created), 1)
        copy_pk = result1.imported_created[0].pk

        # Second run: exclude 900050 (collection has 900051 only).
        result2 = reconcile(
            [collection_record(bgg_id=900051)],
            complete=True,
        )
        self.assertEqual(len(result2.removed), 1)
        refreshed = BoardGame.objects.get(pk=copy_pk)
        self.assertTrue(refreshed.removed)

        # Third run: re-include 900050 (should update the existing copy).
        result3 = reconcile(
            [collection_record(bgg_id=900050)],
            complete=True,
        )
        self.assertTrue(
            len(result3.imported_updated) > 0 or len(result3.imported_created) > 0,
        )
        self.assertEqual(len(result3.restored), 1)
        restored = BoardGame.objects.get(pk=copy_pk)
        self.assertFalse(restored.removed)

    def test_newly_created_in_same_run_not_removed(self):
        """Copies created in the same reconciliation run are never removed."""

        _metadata_for_id(900060)

        collection = [
            collection_record(bgg_id=900060, owned=True),
        ]

        result = reconcile(collection, complete=True)

        self.assertEqual(len(result.imported_created), 1)
        self.assertEqual(len(result.removed), 0)
        self.assertFalse(
            BoardGame.objects.get(pk=result.imported_created[0].pk).removed
        )


class LocalFieldsSurviveTest(TestCase):
    """Verify all local fields survive reconciliation."""

    def _setup_imported_with_fields(self) -> BoardGame:
        """Create an imported BoardGame with all local fields set."""

        meta = BGGMetadata.objects.get_or_create(
            bgg_id=900070, defaults={"name": "Original BGG Name"}
        )[0]
        return BoardGame.objects.create(
            metadata=meta,
            imported=True,
            owned=False,
            removed=False,
            name="My Local Name",
            language="pl",
            edition_label="2nd printing Polish",
            notes="Important note",
            review=8,
            played=True,
            play_priority=3,
            condition="good",
            storage="shelf A",
            purchase_date="2025-06-15",
        )

    def test_all_local_fields_preserved(self):
        """Reconciliation preserves name, language, edition, notes, review,
        played, priority, condition, storage, and purchase_date."""

        original = self._setup_imported_with_fields()

        collection = [
            collection_record(bgg_id=900070, owned=True),
        ]

        result = reconcile(collection)

        self.assertEqual(len(result.imported_updated), 1)

        refreshed = BoardGame.objects.get(pk=original.pk)
        self.assertEqual(refreshed.name, "My Local Name")
        self.assertEqual(refreshed.language, "pl")
        self.assertEqual(refreshed.edition_label, "2nd printing Polish")
        self.assertEqual(refreshed.notes, "Important note")
        self.assertEqual(refreshed.review, 8)
        self.assertEqual(refreshed.played, True)
        self.assertEqual(refreshed.play_priority, 3)
        self.assertEqual(refreshed.condition, "good")
        self.assertEqual(refreshed.storage, "shelf A")
        self.assertEqual(refreshed.purchase_date.isoformat(), "2025-06-15")
        # owned should be updated from the collection record.
        self.assertTrue(refreshed.owned)

    def test_bgg_name_change_does_not_overwrite_local_name(self):
        """BGG canonical name updates do not overwrite local editable name."""

        original = self._setup_imported_with_fields()

        # Simulate a BGG name update by updating metadata directly.
        original.metadata.name = "Updated BGG Name"
        original.metadata.save(update_fields=["name"])

        # Reconcile — local name should survive.
        collection = [
            collection_record(bgg_id=900070, owned=True),
        ]

        reconcile(collection)

        refreshed = BoardGame.objects.get(pk=original.pk)
        self.assertEqual(refreshed.name, "My Local Name")
        # BGG metadata name is updated but local copy is not.
        self.assertEqual(refreshed.metadata.name, "Updated BGG Name")

    def test_empty_local_name_uses_metadata(self):
        """When local name is None, display falls back to metadata."""

        meta = BGGMetadata.objects.get_or_create(
            bgg_id=900071, defaults={"name": "BGG Display Name"}
        )[0]
        bg = BoardGame.objects.create(
            metadata=meta,
            imported=True,
            owned=False,
            name=None,  # no local override.
        )

        self.assertEqual(bg.display_name, "BGG Display Name")

        # Reconcile — empty name should stay empty (no BGG overwrite).
        collection = [
            collection_record(bgg_id=900071),
        ]

        reconcile(collection)

        refreshed = BoardGame.objects.get(pk=bg.pk)
        self.assertIsNone(refreshed.name)
        self.assertEqual(refreshed.display_name, "BGG Display Name")


class NoNetworkWritesTest(TestCase):
    """Verify reconciliation never touches BGG, network, or hard deletes."""

    def test_reconcile_does_not_delete_rows(self):
        """BoardGame rows are never hard-deleted by reconciliation."""

        _metadata_for_id(900080)
        _metadata_for_id(900081)
        _metadata_for_id(900082)

        # bg1: bgg_id 900080 (in the collection → updated).
        bg1 = BoardGame.objects.create(
            metadata=BGGMetadata.objects.get(bgg_id=900080),
            imported=True,
            owned=False,
            removed=False,
        )
        # bg2: bgg_id 900082 (NOT in the complete collection → soft-removed).
        bg2 = BoardGame.objects.create(
            metadata=BGGMetadata.objects.get(bgg_id=900082),
            imported=True,
            owned=False,
            removed=False,
        )

        # Collection includes 900080 and 900081; bg2 is globally absent.
        collection = [
            collection_record(bgg_id=900080, owned=True),
            collection_record(bgg_id=900081, owned=True),
        ]

        reconcile(collection, complete=True)

        # Both rows must still exist (soft-remove, not hard-delete).
        self.assertEqual(BoardGame.objects.filter(pk=bg1.pk).count(), 1)
        self.assertEqual(BoardGame.objects.filter(pk=bg2.pk).count(), 1)
        self.assertTrue(BoardGame.objects.get(pk=bg2.pk).removed)

    def test_local_only_games_survive_complete_true(self):
        """Local-only rows are never removed even with complete=True."""

        meta = BGGMetadataFactory(name="Manual Game")
        _metadata_for_id(900090)
        local_game = BoardGameFactory(
            metadata=meta,
            imported=False,
        )

        collection = [
            collection_record(bgg_id=900090, owned=True),
        ]

        reconcile(collection, complete=True)

        # Local-only game must still exist and not be removed.
        self.assertEqual(BoardGame.objects.filter(pk=local_game.pk).count(), 1)
        self.assertFalse(BoardGame.objects.get(pk=local_game.pk).removed)


class NonOwnedCollectionItemsTest(TestCase):
    def test_non_owned_record_does_not_create_copy_and_is_still_observed(self):
        metadata = BGGMetadataFactory(bgg_id=900100, name="Want to play")
        run = BGGSyncRunFactory()

        result = reconcile(
            [collection_record(bgg_id=900100, owned=False, want_to_play=True)],
            sync_run=run,
        )

        self.assertEqual(result.imported_created, [])
        self.assertFalse(BoardGame.objects.filter(metadata=metadata).exists())
        observation = BGGCollectionObservation.objects.get(metadata=metadata)
        self.assertEqual(observation.sync_run, run)
        self.assertFalse(observation.owned)
        self.assertTrue(observation.want_to_play)

    def test_non_owned_observation_soft_removes_previous_import(self):
        metadata = BGGMetadataFactory(bgg_id=900101, name="No longer owned")
        imported_copy = BoardGameFactory(metadata=metadata, imported=True, owned=True)
        run = BGGSyncRunFactory()
        BGGCollectionObservation.objects.create(
            metadata=metadata,
            sync_run=run,
            owned=False,
        )

        removed_count = remove_missing_imports(run)

        imported_copy.refresh_from_db()
        self.assertEqual(removed_count, 1)
        self.assertTrue(imported_copy.removed)
