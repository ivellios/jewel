"""Focused admin tests for the boardgames app.

Verifies:
- BoardGame: local fields editable, source/ownership/state read-only.
- BGGMetadata: fully read-only (no add/change/delete).
- BGGExpansion: fully read-only.
- BGGSyncRun: fully read-only with list/filter/search.
- Existing games admin tests remain unaffected.
"""

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from boardgames.admin import (
    BGGExpansionAdmin,
    BGGMetadataAdmin,
    BGGSyncRunAdmin,
    BoardGameAdmin,
)
from boardgames.models import (
    BGGExpansion,
    BGGMetadata,
    BGGSyncRun,
    BoardGame,
)

from .factories import (
    BGGExpansionFactory,
    BGGMetadataFactory,
    BGGSyncRunFactory,
    BoardGameFactory,
)


def _make_request(user=None, **kwargs):
    """Create a minimal RequestFactory request."""
    request = RequestFactory().get("/admin/")
    request.user = user
    return request


# ------------------------------------------------------------------ #
# BoardGameAdmin tests
# ------------------------------------------------------------------ #


class BoardGameAdminTest(TestCase):
    """BoardGameAdmin: editable local fields, read-only source/ownership."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = BoardGameAdmin(BoardGame, self.site)

    def test_fields_contains_editable_local_fields(self):
        """Editable local fields are listed in ``fields``."""
        expected = [
            "name",
            "language",
            "edition_label",
            "condition",
            "storage",
            "purchase_date",
        ]
        self.assertEqual(self.admin.fields, expected)

    def test_readonly_fields_contains_source_fields(self):
        """Source/ownership/state fields are read-only."""
        expected = ["metadata", "imported", "owned", "removed"]
        self.assertEqual(self.admin.readonly_fields, expected)

    def test_local_name_is_editable(self):
        """Editable name is in fields, imported is read-only."""
        # ``name`` is in editable fields, ``imported`` is read-only.
        self.assertIn("name", self.admin.fields)
        self.assertNotIn("imported", self.admin.fields)
        self.assertIn("imported", self.admin.readonly_fields)

    def test_metadata_is_readonly(self):
        """Metadata FK is read-only, cannot be changed via admin."""
        BoardGameFactory()
        self.assertIn("metadata", self.admin.readonly_fields)

    def test_owned_and_removed_are_readonly(self):
        """Ownership and removal flags are read-only."""
        self.assertIn("owned", self.admin.readonly_fields)
        self.assertIn("removed", self.admin.readonly_fields)

    def test_display_name_shows_correct_value(self):
        """display_name admin method returns display_name."""
        bg = BoardGameFactory(name="Test Game")
        self.assertEqual(self.admin.display_name(bg), "Test Game")

    def test_list_filter_fields(self):
        """list_filter includes state and metadata."""
        expected = ["imported", "owned", "removed", "metadata", "language"]
        self.assertEqual(self.admin.list_filter, expected)

    def test_search_fields(self):
        """search_fields searches name and metadata name."""
        expected = ["name", "metadata__name"]
        self.assertEqual(self.admin.search_fields, expected)


# ------------------------------------------------------------------ #
# BGGMetadataAdmin tests
# ------------------------------------------------------------------ #


class BGGMetadataAdminTest(TestCase):
    """BGGMetadataAdmin: fully read-only (no add/change/delete)."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = BGGMetadataAdmin(BGGMetadata, self.site)

    def test_has_add_permission_denied(self):
        """Adding new BGG metadata is not permitted."""
        request = _make_request()
        self.assertFalse(self.admin.has_add_permission(request))

    def test_has_change_permission_denied(self):
        """Changing BGG metadata is not permitted."""
        request = _make_request()
        obj = BGGMetadataFactory()
        self.assertFalse(self.admin.has_change_permission(request, obj))

    def test_has_delete_permission_denied(self):
        """Deleting BGG metadata is not permitted."""
        request = _make_request()
        obj = BGGMetadataFactory()
        self.assertFalse(self.admin.has_delete_permission(request, obj))

    def test_all_fields_readonly(self):
        """All concrete (non-reverse, non-pk) model fields are in readonly_fields."""
        for field in BGGMetadata._meta.fields:
            if field.name == "id":
                continue
            self.assertIn(field.name, self.admin.readonly_fields)

    def test_list_display_shows_key_fields(self):
        """list_display shows bgg_id, name, yearpublished."""
        expected = ["bgg_id", "name", "yearpublished"]
        self.assertEqual(self.admin.list_display, expected)

    def test_search_fields_includes_bgg_id(self):
        """Search can find by bgg_id."""
        self.assertIn("bgg_id", self.admin.search_fields)
        self.assertIn("name", self.admin.search_fields)


# ------------------------------------------------------------------ #
# BGGExpansionAdmin tests
# ------------------------------------------------------------------ #


class BGGExpansionAdminTest(TestCase):
    """BGGExpansionAdmin: fully read-only."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = BGGExpansionAdmin(BGGExpansion, self.site)

    def test_has_add_permission_denied(self):
        request = _make_request()
        self.assertFalse(self.admin.has_add_permission(request))

    def test_has_change_permission_denied(self):
        request = _make_request()
        obj = BGGExpansionFactory()
        self.assertFalse(self.admin.has_change_permission(request, obj))

    def test_has_delete_permission_denied(self):
        request = _make_request()
        obj = BGGExpansionFactory()
        self.assertFalse(self.admin.has_delete_permission(request, obj))

    def test_all_fields_readonly(self):
        """All concrete (non-reverse, non-pk) model fields are in readonly_fields."""
        for field in BGGExpansion._meta.fields:
            if field.name == "id":
                continue
            self.assertIn(field.name, self.admin.readonly_fields)

    def test_list_display_shows_key_fields(self):
        expected = ["expansion", "parent", "exp_type", "order"]
        self.assertEqual(self.admin.list_display, expected)


# ------------------------------------------------------------------ #
# BGGSyncRunAdmin tests
# ------------------------------------------------------------------ #


class BGGSyncRunAdminTest(TestCase):
    """BGGSyncRunAdmin: fully read-only with diagnostics."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = BGGSyncRunAdmin(BGGSyncRun, self.site)

    def test_has_add_permission_denied(self):
        request = _make_request()
        self.assertFalse(self.admin.has_add_permission(request))

    def test_has_change_permission_denied(self):
        request = _make_request()
        obj = BGGSyncRunFactory()
        self.assertFalse(self.admin.has_change_permission(request, obj))

    def test_has_delete_permission_denied(self):
        request = _make_request()
        obj = BGGSyncRunFactory()
        self.assertFalse(self.admin.has_delete_permission(request, obj))

    def test_all_fields_readonly(self):
        """All concrete (non-reverse, non-pk) model fields are in readonly_fields."""
        for field in BGGSyncRun._meta.fields:
            if field.name == "id":
                continue
            self.assertIn(field.name, self.admin.readonly_fields)

    def test_list_display_shows_diagnostics(self):
        """list_display shows status, counters, and timestamp."""
        expected = [
            "pk",
            "status",
            "fetch_successful",
            "items_total",
            "items_fetched",
            "items_failed",
            "created_at",
        ]
        self.assertEqual(self.admin.list_display, expected)

    def test_list_filter_shows_status(self):
        """list_filter includes status for filtering."""
        expected = ["status", "fetch_successful"]
        self.assertEqual(self.admin.list_filter, expected)
