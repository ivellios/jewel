"""Focused model tests for BGGMetadata and BGGSyncRun."""

from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase

from boardgames.models import (
    BGGCollectionObservation,
    BGGMetadata,
    BGGSyncRun,
    BGGSyncRunStatus,
    BoardGame,
)

from .factories import (
    BGGCollectionObservationFactory,
    BGGMetadataFactory,
    BGGSyncRunFactory,
    BoardGameFactory,
)


class BGGMetadataModelTest(TestCase):
    """Verify BGGMetadata model constraints and behavior."""

    def test_str(self):
        """String representation uses BGG ID."""
        meta = BGGMetadata.objects.create(bgg_id=12345)
        self.assertEqual(str(meta), "BGG#12345")

    def test_bgg_id_is_unique(self):
        """Duplicate BGG IDs are rejected at database level."""
        BGGMetadata.objects.create(bgg_id=99999, name="Game One")
        with self.assertRaises(IntegrityError):
            BGGMetadata.objects.create(bgg_id=99999, name="Game Two")

    def test_all_source_fields_nullable(self):
        """Every source field accepts None / empty strings."""
        meta = BGGMetadataFactory(name=None, yearpublished=None, minplayers=None)
        meta.maxplayers = None
        meta.playingtime = None
        meta.min_playing_time = None
        meta.max_playing_time = None
        meta.item_type = None
        meta.comment = None
        meta.bgg_url = None
        meta.thumbnail = None
        meta.image = None
        meta.publishers = None
        meta.designers = None
        meta.mechanics = None
        meta.categories = None
        meta.alternative_names = None
        meta.families = None
        meta.rating_bayes_average = None
        meta.rating_average = None
        meta.rating_median = None
        meta.rating_stddev = None
        meta.rating_num_weights = None
        meta.bgg_rank = None
        meta.boardgame_rank = None
        meta.users_rated = None
        meta.users_owned = None
        meta.plays_count = None
        meta.save()

        # Reload and verify all fields are None or blank.
        refreshed = BGGMetadata.objects.get(pk=meta.pk)
        self.assertIsNone(refreshed.name)
        self.assertIsNone(refreshed.yearpublished)
        self.assertIsNone(refreshed.minplayers)
        self.assertIsNone(refreshed.maxplayers)
        self.assertIsNone(refreshed.playingtime)
        self.assertIsNone(refreshed.min_playing_time)
        self.assertIsNone(refreshed.max_playing_time)
        self.assertIsNone(refreshed.item_type)
        self.assertIsNone(refreshed.comment)
        self.assertIsNone(refreshed.bgg_url)
        self.assertIsNone(refreshed.thumbnail)
        self.assertIsNone(refreshed.image)
        self.assertIsNone(refreshed.publishers)
        self.assertIsNone(refreshed.designers)
        self.assertIsNone(refreshed.mechanics)
        self.assertIsNone(refreshed.categories)
        self.assertIsNone(refreshed.alternative_names)
        self.assertIsNone(refreshed.families)
        self.assertIsNone(refreshed.rating_bayes_average)
        self.assertIsNone(refreshed.rating_average)
        self.assertIsNone(refreshed.rating_median)
        self.assertIsNone(refreshed.rating_stddev)
        self.assertIsNone(refreshed.rating_num_weights)
        self.assertIsNone(refreshed.bgg_rank)
        self.assertIsNone(refreshed.boardgame_rank)
        self.assertIsNone(refreshed.users_rated)
        self.assertIsNone(refreshed.users_owned)
        self.assertIsNone(refreshed.plays_count)

    def test_minplayers_validator(self):
        """minplayers rejects values below 1."""
        meta = BGGMetadata(bgg_id=80000, name="Test", minplayers=0)
        with self.assertRaises(ValidationError):
            meta.full_clean()

    def test_maxplayers_validator(self):
        """maxplayers rejects values below 1."""
        meta = BGGMetadata(bgg_id=80001, name="Test", maxplayers=0)
        with self.assertRaises(ValidationError):
            meta.full_clean()

    def test_default_ordering(self):
        """QuerySet orders by bgg_id ascending."""
        BGGMetadata.objects.create(bgg_id=300, name="C")
        BGGMetadata.objects.create(bgg_id=100, name="A")
        BGGMetadata.objects.create(bgg_id=200, name="B")

        ids = list(BGGMetadata.objects.values_list("bgg_id", flat=True))
        self.assertEqual(ids, [100, 200, 300])


class BGGSyncRunModelTest(TestCase):
    """Verify BGGSyncRun model constraints and behavior."""

    def test_str(self):
        """String representation uses status."""
        run = BGGSyncRun.objects.create(
            status=BGGSyncRunStatus.FULL,
        )
        self.assertIn("full", str(run))
        self.assertIn("BGGSyncRun#", str(run))

    def test_default_status_is_failed(self):
        """Unset status defaults to 'failed'."""
        run = BGGSyncRun.objects.create()
        self.assertEqual(run.status, BGGSyncRunStatus.FAILED)

    def test_fetch_successful_defaults_false(self):
        """fetch_successful defaults to False."""
        run = BGGSyncRun.objects.create()
        self.assertFalse(run.fetch_successful)

    def test_counters_default_to_zero(self):
        """All counters default to 0."""
        run = BGGSyncRun.objects.create()
        self.assertEqual(run.items_total, 0)
        self.assertEqual(run.items_fetched, 0)
        self.assertEqual(run.items_failed, 0)

    def test_timestamps_created_at_auto(self):
        """created_at is set automatically."""
        run = BGGSyncRun.objects.create()
        self.assertIsNotNone(run.created_at)

    def test_completed_at_can_be_null(self):
        """completed_at defaults to None until completion."""
        run = BGGSyncRun.objects.create()
        self.assertIsNone(run.completed_at)

    def test_null_error_and_diagnostics(self):
        """error_messages and diagnostics accept None."""
        BGGSyncRun.objects.create(
            status=BGGSyncRunStatus.PARTIAL,
            error_messages=None,
            diagnostics=None,
        )

    def test_status_choices(self):
        """Status is one of the defined choices."""
        valid_choices = dict(BGGSyncRunStatus.choices)
        self.assertIn("full", valid_choices)
        self.assertIn("partial", valid_choices)
        self.assertIn("failed", valid_choices)

    def test_lifecycle_full_to_failed(self):
        """A run can transition between statuses."""
        run = BGGSyncRun.objects.create(
            status=BGGSyncRunStatus.FULL,
            fetch_successful=True,
            items_total=100,
            items_fetched=100,
            items_failed=0,
        )

        # Transition to partial with some errors.
        run.status = BGGSyncRunStatus.PARTIAL
        run.fetch_successful = False
        run.items_total = 100
        run.items_fetched = 90
        run.items_failed = 10
        run.error_messages = "3 items failed with network errors"
        run.diagnostics = "Total errors: 3, retry limit reached"
        run.completed_at = run.created_at  # same timestamp for test
        run.save()

        refreshed = BGGSyncRun.objects.get(pk=run.pk)
        self.assertEqual(refreshed.status, BGGSyncRunStatus.PARTIAL)
        self.assertFalse(refreshed.fetch_successful)
        self.assertEqual(refreshed.items_failed, 10)
        self.assertIsNotNone(refreshed.error_messages)
        self.assertIsNotNone(refreshed.diagnostics)


class BGGCollectionObservationModelTest(TestCase):
    """Verify configured-account collection state stays separate from copies."""

    def test_observation_tracks_quantity_and_flags_for_canonical_game(self):
        metadata = BGGMetadataFactory()
        sync_run = BGGSyncRunFactory()
        observation = BGGCollectionObservationFactory(
            metadata=metadata,
            sync_run=sync_run,
            quantity=3,
            owned=True,
            wishlist=False,
            want_to_play=True,
        )

        self.assertEqual(observation.metadata, metadata)
        self.assertEqual(observation.sync_run, sync_run)
        self.assertEqual(observation.quantity, 3)
        self.assertTrue(observation.owned)
        self.assertFalse(observation.wishlist)
        self.assertTrue(observation.want_to_play)
        self.assertEqual(metadata.copies.count(), 0)

    def test_only_one_latest_observation_exists_per_canonical_game(self):
        metadata = BGGMetadataFactory()
        BGGCollectionObservationFactory(metadata=metadata)

        with self.assertRaises(IntegrityError):
            BGGCollectionObservationFactory(metadata=metadata)

    def test_observation_source_values_can_be_omitted(self):
        observation = BGGCollectionObservationFactory(
            quantity=None,
            rating=None,
            numplays=None,
            owned=None,
            wishlist=None,
            want_to_play=None,
        )

        observation.refresh_from_db()
        self.assertIsNone(observation.quantity)
        self.assertIsNone(observation.rating)
        self.assertIsNone(observation.numplays)
        self.assertIsNone(observation.owned)
        self.assertIsNone(observation.wishlist)
        self.assertIsNone(observation.want_to_play)

    def test_quantity_rejects_negative_values(self):
        observation = BGGCollectionObservation(
            metadata=BGGMetadataFactory(),
            quantity=-1,
        )

        with self.assertRaises(ValidationError):
            observation.full_clean()


class BoardGameModelTest(TestCase):
    """Verify BoardGame model constraints and behaviour."""

    def test_uuid_primary_key(self):
        """BoardGame uses UUID primary key."""
        bg = BoardGameFactory()
        self.assertIsNotNone(bg.id)
        self.assertEqual(type(bg.id).__name__, "UUID")

    def test_str_uses_editable_name(self):
        """__str__ returns the editable name when set."""
        bg = BoardGameFactory(name="Gloomhaven")
        self.assertEqual(str(bg), "Gloomhaven")

    def test_str_falls_back_to_metadata_name(self):
        """__str__ falls back to linked metadata name."""
        meta = BGGMetadataFactory(name="Catan")
        bg = BoardGameFactory(metadata=meta, name=None)
        self.assertEqual(str(bg), "Catan")

    def test_str_falls_back_to_base_name(self):
        """__str__ falls back to CollectionItem base name."""
        bg = BoardGameFactory(name=None, metadata__name=None)
        # CollectionItem provides a default faker name
        self.assertNotEqual(str(bg), "")

    def test_metadata_is_optional(self):
        """BoardGame can exist without linked BGG metadata."""
        bg = BoardGameFactory(metadata=None)
        self.assertIsNone(bg.metadata)

    def test_editable_name_overrides_metadata_name(self):
        """Local editable name takes priority over metadata name."""
        meta = BGGMetadataFactory(name="Carcassonne")
        bg = BoardGameFactory(metadata=meta, name="Carcassonne (local name)")
        self.assertEqual(bg.display_name, "Carcassonne (local name)")

    def test_local_only_copy_has_no_metadata(self):
        """Local/manual copies have metadata=None and imported=False."""
        bg = BoardGameFactory(metadata=None, imported=False)
        self.assertIsNone(bg.metadata)
        self.assertFalse(bg.imported)

    def test_imported_flag_set_on_sync_copy(self):
        """Imported copies track BGG origin explicitly."""
        meta = BGGMetadataFactory(name="Pandemic")
        bg = BoardGameFactory(metadata=meta, imported=True, owned=True)
        self.assertTrue(bg.imported)
        self.assertTrue(bg.owned)

    def test_owned_and_removed_fields(self):
        """owned and removed are independent boolean flags."""
        bg = BoardGameFactory(owned=True, removed=False)
        self.assertTrue(bg.owned)
        self.assertFalse(bg.removed)

        bg.removed = True
        bg.save()
        refreshed = BoardGame.objects.get(pk=bg.pk)
        self.assertTrue(refreshed.owned)
        self.assertTrue(refreshed.removed)

    def test_local_copy_does_not_affect_metadata(self):
        """Removing a BoardGame copy does not affect BGGMetadata."""
        meta = BGGMetadataFactory(name="Wingspan")
        meta_copy_count = BGGMetadata.objects.filter(name="Wingspan").count()
        BoardGameFactory(metadata=meta, imported=True)
        self.assertEqual(
            BGGMetadata.objects.filter(name="Wingspan").count(), meta_copy_count
        )

    def test_multiple_copies_share_same_metadata(self):
        """Multiple BoardGame rows can reference the same BGGMetadata."""
        meta = BGGMetadataFactory(name="Azul")
        BoardGameFactory(metadata=meta, name="Azul copy 1")
        BoardGameFactory(metadata=meta, name="Azul copy 2")
        self.assertEqual(BoardGame.objects.filter(metadata=meta).count(), 2)

    def test_distinct_metadata_ids_produce_distinct_copies(self):
        """Different BGG metadata IDs yield distinct BoardGame rows."""
        meta_a = BGGMetadataFactory(name="Ticket to Ride")
        meta_b = BGGMetadataFactory(name="Ticket to Ride: Europe")
        bg_a = BoardGameFactory(metadata=meta_a, name="TTR")
        bg_b = BoardGameFactory(metadata=meta_b, name="TTR Europe")
        self.assertNotEqual(bg_a.id, bg_b.id)
        self.assertNotEqual(bg_a.metadata_id, bg_b.metadata_id)

    def test_non_metadata_boardgame_has_no_metadata_link(self):
        """BoardGame without metadata has no metadata FK set."""
        bg = BoardGameFactory(metadata=None)
        self.assertIsNone(bg.metadata_id)
