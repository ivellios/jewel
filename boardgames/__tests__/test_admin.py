"""Focused admin tests for Packet 11 — Admin ownership and reversible-removal contract.

Verifies:
- BoardGame: fieldsets separate editable local + inherited fields from
  read-only BGG source / ownership / removal state.
- Inherited CollectionItem fields (played, review, notes, play_priority,
  min_players, max_players) are editable within the local-data fieldset.
- metadata (BGG FK), imported, owned, removed remain read-only.
- ``has_delete_permission`` blocks hard-deletion of imported rows,
  while allowing deletion of local-only rows.
- ``metadata_link`` and ``state`` display helpers render correctly.
- Existing game admin tests remain unaffected.
"""

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
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
# BoardGameAdmin — fieldsets
# ------------------------------------------------------------------ #


class BoardGameFieldsetsTest(TestCase):
    """BoardGameAdmin: fieldsets separate editable and read-only data."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = BoardGameAdmin(BoardGame, self.site)

    def test_fieldsets_exist_and_have_two_sections(self):
        """Two fieldsets: local data (editable) and source/ownership (read-only)."""
        self.assertEqual(len(self.admin.fieldsets), 2)
        labels = [section[0] for section in self.admin.fieldsets]
        self.assertIn("Local physical-copy data (editable)", labels)
        self.assertIn("BGG source identity & ownership state (read-only)", labels)

    def test_editable_local_fields_all_present(self):
        """All BoardGame local fields appear in the first fieldset."""
        local_fields = self.admin.fieldsets[0][1]["fields"]
        expected_local = (
            "name",
            "language",
            "edition_label",
            "condition",
            "storage",
            "purchase_date",
            "played",
            "review",
            "notes",
            "play_priority",
            "min_players",
            "max_players",
        )
        self.assertEqual(local_fields, expected_local)

    def test_inherited_collectionitem_fields_in_editable(self):
        """Inherited CollectionItem fields (played, review, notes, play_priority,
        min_players, max_players) are in the editable fieldset."""
        local_fields = self.admin.fieldsets[0][1]["fields"]
        inherited = (
            "played",
            "review",
            "notes",
            "play_priority",
            "min_players",
            "max_players",
        )
        for field in inherited:
            self.assertIn(field, local_fields)

    def test_source_state_fieldset_is_collapsed(self):
        """Source/ownership fieldset is collapsed to keep focus on local data."""
        source_fields = self.admin.fieldsets[1][1]
        self.assertIn("collapse", source_fields.get("classes", []))

    def test_source_fields_are_readonly(self):
        """metadata, imported, owned, removed are in readonly_fields."""
        expected_readonly = (
            "metadata",
            "imported",
            "owned",
            "removed",
        )
        for field in expected_readonly:
            self.assertIn(field, self.admin.readonly_fields)

    def test_source_state_not_in_editable_fieldset(self):
        """Imported/owned/removed/metadata are NOT in the editable (first) fieldset."""
        editable_fields = self.admin.fieldsets[0][1]["fields"]
        for protected in ("imported", "owned", "removed", "metadata"):
            self.assertNotIn(protected, editable_fields)


# ------------------------------------------------------------------ #
# BoardGameAdmin — display helpers
# ------------------------------------------------------------------ #


class BoardGameDisplayHelpersTest(TestCase):
    """Test metadata_link and state display helpers."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = BoardGameAdmin(BoardGame, self.site)

    def test_metadata_link_for_imported(self):
        """metadata_link renders a BGG link when metadata exists."""
        metadata = BGGMetadataFactory(bgg_id=12345)
        bg = BoardGameFactory(metadata=metadata, imported=True)
        result = self.admin.metadata_link(bg)
        self.assertIn("BGG #12345", result)
        self.assertIn('href="https://boardgamegeek.com/boardgame/', result)

    def test_metadata_link_for_local_only(self):
        """metadata_link shows '— (local-only)' when no metadata."""
        bg = BoardGameFactory(metadata=None, imported=False)
        result = self.admin.metadata_link(bg)
        self.assertIn("local-only", result)

    def test_state_imported(self):
        """state shows 'Imported' for imported copies."""
        bg = BoardGameFactory(imported=True)
        result = self.admin.state(bg)
        self.assertIn("Imported", result)

    def test_state_local_only(self):
        """state shows 'Local-only' for non-imported copies."""
        bg = BoardGameFactory(imported=False)
        result = self.admin.state(bg)
        self.assertIn("Local-only", result)


# ------------------------------------------------------------------ #
# BoardGameAdmin — deletion guard
# ------------------------------------------------------------------ #


class BoardGameDeletionGuardTest(TestCase):
    """BoardGameAdmin: imported copies cannot be hard-deleted from admin."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = BoardGameAdmin(BoardGame, self.site)
        # Create a superuser with proper permissions for deletion checks.
        self.superuser = User.objects.create_superuser(
            "admin", "admin@test.com", "pass"
        )
        self.superuser.save()
        self.admin_request = _make_request(self.superuser)

    def test_imported_copy_cannot_be_deleted(self):
        """has_delete_permission returns False for imported copies."""
        bg = BoardGameFactory(imported=True)
        self.assertFalse(self.admin.has_delete_permission(self.admin_request, bg))

    def test_local_only_copy_can_be_deleted(self):
        """has_delete_permission returns True for local-only copies."""
        bg = BoardGameFactory(imported=False)
        self.assertTrue(self.admin.has_delete_permission(self.admin_request, bg))

    def test_delete_permission_with_no_object(self):
        """has_delete_permission defers to parent when obj is None."""
        # When obj is None (changelist bulk delete), the permission
        # should be the default (True for superusers).
        self.assertTrue(self.admin.has_delete_permission(self.admin_request, None))

    def test_delete_permission_with_regular_user_cannot_delete_imported(self):
        """Regular users without delete permission cannot delete imported copies."""
        regular_user = User.objects.create_user("viewer", "viewer@test.com", "pass")
        regular_user.save()
        viewer_request = _make_request(regular_user)
        bg = BoardGameFactory(imported=True)
        self.assertFalse(self.admin.has_delete_permission(viewer_request, bg))


# ------------------------------------------------------------------ #
# BGGMetadataAdmin (unchanged from previous packets)
# ------------------------------------------------------------------ #


class BGGMetadataAdminTest(TestCase):
    """BGGMetadataAdmin: fully read-only (no add/change/delete)."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = BGGMetadataAdmin(BGGMetadata, self.site)

    def test_has_add_permission_denied(self):
        request = _make_request()
        self.assertFalse(self.admin.has_add_permission(request))

    def test_has_change_permission_denied(self):
        request = _make_request()
        obj = BGGMetadataFactory()
        self.assertFalse(self.admin.has_change_permission(request, obj))

    def test_has_delete_permission_denied(self):
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
        expected = ["bgg_id", "name", "yearpublished"]
        self.assertEqual(self.admin.list_display, expected)

    def test_search_fields_includes_bgg_id(self):
        self.assertIn("bgg_id", self.admin.search_fields)
        self.assertIn("name", self.admin.search_fields)


# ------------------------------------------------------------------ #
# BGGExpansionAdmin (unchanged)
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
        for field in BGGExpansion._meta.fields:
            if field.name == "id":
                continue
            self.assertIn(field.name, self.admin.readonly_fields)

    def test_list_display_shows_key_fields(self):
        expected = ["expansion", "parent", "exp_type", "order"]
        self.assertEqual(self.admin.list_display, expected)


# ------------------------------------------------------------------ #
# BGGSyncRunAdmin (unchanged)
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
        for field in BGGSyncRun._meta.fields:
            if field.name == "id":
                continue
            self.assertIn(field.name, self.admin.readonly_fields)

    def test_list_display_shows_diagnostics(self):
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
        expected = ["status", "fetch_successful"]
        self.assertEqual(self.admin.list_filter, expected)


# ------------------------------------------------------------------ #
# Existing BoardGameAdmin tests (legacy — should still pass)
# ------------------------------------------------------------------ #


class LegacyBoardGameAdminTest(TestCase):
    """Ensure existing game admin expectations are not broken by Packet 11."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = BoardGameAdmin(BoardGame, self.site)

    def test_local_name_is_editable(self):
        editable_fields = self.admin.fieldsets[0][1]["fields"]
        self.assertIn("name", editable_fields)
        self.assertIn("imported", self.admin.readonly_fields)

    def test_metadata_is_readonly(self):
        BoardGameFactory()
        self.assertIn("metadata", self.admin.readonly_fields)

    def test_owned_and_removed_are_readonly(self):
        self.assertIn("owned", self.admin.readonly_fields)
        self.assertIn("removed", self.admin.readonly_fields)

    def test_display_name_shows_correct_value(self):
        bg = BoardGameFactory(name="Test Game")
        self.assertEqual(self.admin.display_name(bg), "Test Game")

    def test_list_filter_fields(self):
        expected = ["imported", "owned", "removed", "metadata", "language"]
        self.assertEqual(self.admin.list_filter, expected)

    def test_search_fields(self):
        expected = ["name", "metadata__name"]
        self.assertEqual(self.admin.search_fields, expected)
