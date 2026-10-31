"""Focused model tests for BGGMetadata and BGGSyncRun."""

from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase

from boardgames.models import BGGMetadata, BGGSyncRun, BGGSyncRunStatus

from .factories import BGGMetadataFactory


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
        meta.comment = None
        meta.thumbnail = None
        meta.image = None
        meta.publishers = None
        meta.designers = None
        meta.mechanics = None
        meta.categories = None
        meta.save()

        # Reload and verify all fields are None or blank.
        refreshed = BGGMetadata.objects.get(pk=meta.pk)
        self.assertIsNone(refreshed.name)
        self.assertIsNone(refreshed.yearpublished)
        self.assertIsNone(refreshed.minplayers)
        self.assertIsNone(refreshed.maxplayers)
        self.assertIsNone(refreshed.playingtime)
        self.assertIsNone(refreshed.comment)
        self.assertIsNone(refreshed.thumbnail)
        self.assertIsNone(refreshed.image)
        self.assertIsNone(refreshed.publishers)
        self.assertIsNone(refreshed.designers)
        self.assertIsNone(refreshed.mechanics)
        self.assertIsNone(refreshed.categories)

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
