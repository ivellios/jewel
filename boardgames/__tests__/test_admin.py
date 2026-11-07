"""Focused admin tests for Packet 11 — Admin ownership and reversible-removal contract.

Verifies:
- BoardGame: fieldsets separate editable local + inherited fields from
  read-only BGG source / ownership / removal state.
- Inherited CollectionItem fields (played, review, notes, play_priority,
  min_players, max_players) are editable within the local-data fieldset.
- metadata (BGG FK), imported, owned, removed remain read-only.
- ``has_delete_permission`` blocks hard-deletion of imported rows,
  while allowing deletion of local-only rows.
- ``metadata_link`` display helper renders correctly.
- Existing game admin tests remain unaffected.
"""

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse

from boardgames.admin import (
    BGGExpansionAdmin,
    BGGMetadataAdmin,
    BGGSyncRunAdmin,
    BoardGameAdmin,
    HasBGGRankFilter,
    OfficialPlayerCountFilter,
    PlayingTimeFilter,
    ShowExpansionsFilter,
    ShowRemovedFilter,
)
from boardgames.models import (
    BGGCollectionObservation,
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
        """Separate local data, source/ownership, and expansion sections."""
        self.assertEqual(len(self.admin.fieldsets), 3)
        labels = [section[0] for section in self.admin.fieldsets]
        self.assertIn("Local physical-copy data (editable)", labels)
        self.assertIn("BGG source identity & ownership state (read-only)", labels)
        self.assertIn("Expansions", labels)

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
            "metadata_link",
            "imported",
            "owned",
            "removed",
        )
        for field in expected_readonly:
            self.assertIn(field, self.admin.readonly_fields)
        self.assertIn("metadata_link", self.admin.fieldsets[1][1]["fields"])

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
        metadata = BGGMetadataFactory(bgg_id=12345, name="Ticket to Ride")
        bg = BoardGameFactory(metadata=metadata, imported=True)
        result = self.admin.metadata_link(bg)
        self.assertIn("BGG Link", result)
        self.assertNotIn("Ticket to Ride", result)
        self.assertIn('href="https://boardgamegeek.com/boardgame/', result)

    def test_metadata_link_for_local_only(self):
        """metadata_link shows '— (local-only)' when no metadata."""
        bg = BoardGameFactory(metadata=None, imported=False)
        result = self.admin.metadata_link(bg)
        self.assertIn("local-only", result)

    def test_bgg_summary_values_are_available_on_local_copy(self):
        metadata = BGGMetadataFactory(
            bgg_id=12346,
            rating_average=7.8,
            boardgame_rank=42,
        )
        BGGCollectionObservation.objects.create(metadata=metadata, numplays=5)
        game = BoardGameFactory(metadata=metadata)

        self.assertEqual(self.admin.bgg_plays(game), 5)
        self.assertEqual(self.admin.bgg_rating(game), 7.8)
        self.assertEqual(self.admin.bgg_rank(game), 42)

    def test_bgg_summary_values_are_blank_without_metadata(self):
        game = BoardGameFactory(metadata=None, imported=False)

        self.assertEqual(self.admin.bgg_plays(game), "—")
        self.assertEqual(self.admin.bgg_rating(game), "—")
        self.assertEqual(self.admin.bgg_rank(game), "—")

    def test_expansion_links_list_all_children_and_link_to_copy_or_bgg(self):
        parent = BGGMetadataFactory(bgg_id=12350, name="Base game")
        local_expansion = BGGMetadataFactory(
            bgg_id=12351,
            name="Local deck",
            rating_average=7.4,
            boardgame_rank=12,
            minplayers=1,
            maxplayers=4,
            playingtime=90,
        )
        remote_expansion = BGGMetadataFactory(bgg_id=12352, name="Remote deck")
        BGGExpansionFactory(expansion=local_expansion, parent=parent)
        BGGExpansionFactory(expansion=remote_expansion, parent=parent)
        BGGCollectionObservation.objects.create(
            metadata=local_expansion,
            numplays=3,
            owned=True,
        )
        local_copy = BoardGameFactory(metadata=local_expansion, name="My local deck")
        game = BoardGameFactory(metadata=parent)

        result = self.admin.expansion_links(game)

        self.assertIn("My local deck", result)
        self.assertIn(
            reverse("admin:boardgames_boardgame_change", args=[local_copy.pk]),
            result,
        )
        self.assertIn("Remote deck", result)
        self.assertIn("https://boardgamegeek.com/boardgame/12352", result)
        for detail in (
            "BGG rating",
            "Rank",
            "Your plays",
            "Players",
            "Playing time",
            "In collection",
            "7.4",
            "12",
            "3",
            "1–4",
            "90 min",
            "Yes",
        ):
            self.assertIn(detail, result)
        self.assertIn("expansion_links", self.admin.readonly_fields)

    def test_bgg_summary_values_are_listed_for_local_copies(self):
        self.assertIn("bgg_plays", self.admin.list_display)
        self.assertIn("bgg_rating", self.admin.list_display)
        self.assertIn("bgg_rank", self.admin.list_display)
        self.assertIn("bgg_plays", self.admin.readonly_fields)
        self.assertIn("bgg_rating", self.admin.readonly_fields)
        self.assertIn("bgg_rank", self.admin.readonly_fields)

    def test_changelist_uses_rank_and_expansion_filters_not_metadata_filter(self):
        self.assertIn(HasBGGRankFilter, self.admin.list_filter)
        self.assertIn(PlayingTimeFilter, self.admin.list_filter)
        self.assertIn(ShowExpansionsFilter, self.admin.list_filter)
        self.assertIn(ShowRemovedFilter, self.admin.list_filter)
        self.assertNotIn("metadata", self.admin.list_filter)

    def test_official_player_range_shortcut(self):
        self.assertIn("official_player_range", self.admin.list_display)
        self.assertIn("official_player_range", self.admin.readonly_fields)

    def test_community_player_labels_shortcut(self):
        self.assertIn("community_player_labels", self.admin.list_display)
        self.assertIn("community_player_labels", self.admin.readonly_fields)

    def test_best_player_labels_shortcut(self):
        self.assertIn("best_player_labels", self.admin.list_display)
        self.assertIn("best_player_labels", self.admin.readonly_fields)


# ------------------------------------------------------------------ #
# BoardGameAdmin — player-count columns (Packet 3)
# ------------------------------------------------------------------ #


class BoardGamePlayerCountColumnsTest(TestCase):
    """BoardGameAdmin: Official, Community, Best columns."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = BoardGameAdmin(BoardGame, self.site)

    # -- Official --

    def test_official_shows_range_from_metadata(self):
        meta = BGGMetadataFactory(minplayers=2, maxplayers=4)
        bg = BoardGameFactory(metadata=meta)
        self.assertEqual(self.admin.official_player_range(bg), "2–4")

    def test_official_shows_single(self):
        meta = BGGMetadataFactory(minplayers=4, maxplayers=4)
        bg = BoardGameFactory(metadata=meta)
        self.assertEqual(self.admin.official_player_range(bg), "4")

    def test_official_returns_dash_when_no_metadata(self):
        bg = BoardGameFactory(metadata=None)
        self.assertEqual(self.admin.official_player_range(bg), "—")

    def test_official_returns_dash_when_no_players(self):
        meta = BGGMetadataFactory(minplayers=None, maxplayers=None)
        bg = BoardGameFactory(metadata=meta)
        self.assertEqual(self.admin.official_player_range(bg), "—")

    # -- Packet 4: numplayers_summary (poll summary text) --

    def _make_metadata_with_summary(self, bgg_id=300000, **kwargs):
        """Create metadata with numplayers_summary from Mascarade-style data."""
        return BGGMetadataFactory(
            bgg_id=bgg_id,
            numplayers_summary=kwargs.get("numplayers_summary"),
            suggested_players=kwargs.get("suggested"),
            minplayers=kwargs.get("minplayers"),
            maxplayers=kwargs.get("maxplayers"),
        )

    def test_community_shows_only_range_with_plain_hyphen(self):
        """Community column shows recommendedwith from poll summary."""
        meta = self._make_metadata_with_summary(
            numplayers_summary={
                "bestwith": "Best with 6–8 players",
                "recommendedwith": "Recommended with 4–11 players",
            }
        )
        bg = BoardGameFactory(metadata=meta)
        self.assertEqual(
            self.admin.community_player_labels(bg),
            "4-11",
        )

    def test_best_shows_only_range_with_plain_hyphen(self):
        """Best column shows only the compact range from poll summary."""
        meta = self._make_metadata_with_summary(
            numplayers_summary={
                "bestwith": "Best with 6–8 players",
                "recommendedwith": "Recommended with 4–11 players",
            }
        )
        bg = BoardGameFactory(metadata=meta)
        self.assertEqual(self.admin.best_player_labels(bg), "6-8")

    def test_single_player_count_stays_compact(self):
        meta = self._make_metadata_with_summary(
            numplayers_summary={
                "bestwith": "Best with 5 players",
                "recommendedwith": "Recommended with 3 players",
            }
        )
        bg = BoardGameFactory(metadata=meta)

        self.assertEqual(self.admin.community_player_labels(bg), "3")
        self.assertEqual(self.admin.best_player_labels(bg), "5")

    def test_community_returns_dash_without_summary(self):
        """Community shows '—' when numplayers_summary is missing."""
        meta = self._make_metadata_with_summary()
        bg = BoardGameFactory(metadata=meta)
        self.assertEqual(self.admin.community_player_labels(bg), "—")

    def test_best_returns_dash_without_summary(self):
        """Best shows '—' when numplayers_summary is missing."""
        meta = self._make_metadata_with_summary()
        bg = BoardGameFactory(metadata=meta)
        self.assertEqual(self.admin.best_player_labels(bg), "—")

    def test_community_returns_dash_without_metadata(self):
        """Community shows '—' when no metadata at all."""
        bg = BoardGameFactory(metadata=None)
        self.assertEqual(self.admin.community_player_labels(bg), "—")

    def test_best_returns_dash_without_metadata(self):
        """Best shows '—' when no metadata at all."""
        bg = BoardGameFactory(metadata=None)
        self.assertEqual(self.admin.best_player_labels(bg), "—")

    def test_community_missing_bestwith_only(self):
        """When only bestwith present, community shows '—'."""
        meta = BGGMetadataFactory(
            bgg_id=300010,
            numplayers_summary={"bestwith": "Best with 3 players"},
        )
        bg = BoardGameFactory(metadata=meta)
        self.assertEqual(self.admin.community_player_labels(bg), "—")

    def test_best_missing_recommendedwith_only(self):
        """When only recommendedwith present, best shows '—'."""
        meta = BGGMetadataFactory(
            bgg_id=300011,
            numplayers_summary={"recommendedwith": "Recommended with 5 players"},
        )
        bg = BoardGameFactory(metadata=meta)
        self.assertEqual(self.admin.best_player_labels(bg), "—")


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
            if field.name in self.admin.exclude:
                continue
            self.assertIn(field.name, self.admin.readonly_fields)

    def test_list_display_shows_key_fields(self):
        expected = ["bgg_id", "name", "yearpublished", "collection_plays"]
        self.assertEqual(self.admin.list_display, expected)

    def test_collection_plays_reads_user_specific_observation(self):
        metadata = BGGMetadataFactory(bgg_id=12001)
        BGGCollectionObservation.objects.create(metadata=metadata, numplays=4)

        self.assertEqual(self.admin.collection_plays(metadata), 4)

    def test_collection_plays_is_unknown_without_observation(self):
        metadata = BGGMetadataFactory(bgg_id=12002)

        self.assertEqual(self.admin.collection_plays(metadata), "—")
        self.assertIn("plays_count", self.admin.exclude)

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
            if field.name in {"id", "expansion", "parent"}:
                continue
            self.assertIn(field.name, self.admin.readonly_fields)
        self.assertIn("expansion_link", self.admin.readonly_fields)
        self.assertIn("parent_link", self.admin.readonly_fields)

    def test_list_display_shows_key_fields(self):
        expected = ["expansion_link", "parent_link", "exp_type", "order"]
        self.assertEqual(self.admin.list_display, expected)

    def test_expansion_links_to_active_local_copy_by_title(self):
        expansion = BGGMetadataFactory(bgg_id=12011, name="Local expansion title")
        base = BGGMetadataFactory(bgg_id=12012, name="Base game")
        relation = BGGExpansionFactory(expansion=expansion, parent=base)
        copy = BoardGameFactory(metadata=expansion, imported=True, name="My expansion")

        result = self.admin.expansion_link(relation)

        self.assertIn("My expansion", result)
        self.assertIn(
            reverse("admin:boardgames_boardgame_change", args=[copy.pk]), result
        )

    def test_expansion_falls_back_to_named_bgg_page_without_local_copy(self):
        expansion = BGGMetadataFactory(bgg_id=12013, name="BGG title", bgg_url=None)
        relation = BGGExpansionFactory(expansion=expansion)

        result = self.admin.expansion_link(relation)

        self.assertIn("BGG title", result)
        self.assertIn("https://boardgamegeek.com/boardgame/12013", result)


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
        expected = [
            "imported",
            "owned",
            ShowRemovedFilter,
            HasBGGRankFilter,
            PlayingTimeFilter,
            OfficialPlayerCountFilter,
            ShowExpansionsFilter,
            "language",
        ]
        self.assertEqual(self.admin.list_filter, expected)

    def test_search_fields(self):
        expected = ["name", "metadata__name"]
        self.assertEqual(self.admin.search_fields, expected)


class BoardGameListFilterTest(TestCase):
    def setUp(self):
        self.request = _make_request()
        self.model_admin = BoardGameAdmin(BoardGame, AdminSite())

    def make_filter(self, filter_class, params=None):
        return filter_class(
            self.request,
            {key: [value] for key, value in (params or {}).items()},
            BoardGame,
            self.model_admin,
        )

    def test_expansions_are_hidden_by_default_but_local_copies_remain(self):
        base = BGGMetadataFactory(bgg_id=13001, item_type="boardgame")
        expansion = BGGMetadataFactory(
            bgg_id=13002,
            item_type="boardgameexpansion",
        )
        unknown_type = BGGMetadataFactory(bgg_id=13003, item_type=None)
        parent = BGGMetadataFactory(bgg_id=13007, item_type="boardgame")
        linked_expansion = BGGMetadataFactory(bgg_id=13008, item_type=None)
        BGGExpansionFactory(expansion=linked_expansion, parent=parent)
        base_copy = BoardGameFactory(metadata=base)
        expansion_copy = BoardGameFactory(metadata=expansion)
        unknown_copy = BoardGameFactory(metadata=unknown_type)
        linked_expansion_copy = BoardGameFactory(metadata=linked_expansion)
        local_copy = BoardGameFactory(metadata=None, imported=False)

        filtered = self.make_filter(ShowExpansionsFilter).queryset(
            self.request, BoardGame.objects.all()
        )

        self.assertEqual(
            set(filtered.values_list("pk", flat=True)),
            {base_copy.pk, unknown_copy.pk, local_copy.pk},
        )
        self.assertNotIn(expansion_copy.pk, set(filtered.values_list("pk", flat=True)))
        self.assertNotIn(
            linked_expansion_copy.pk,
            set(filtered.values_list("pk", flat=True)),
        )

    def test_expansion_filter_can_include_expansions(self):
        expansion = BGGMetadataFactory(
            bgg_id=13004,
            item_type="boardgameexpansion",
        )
        game = BoardGameFactory(metadata=expansion)

        filtered = self.make_filter(
            ShowExpansionsFilter,
            {"show_expansions": "yes"},
        ).queryset(self.request, BoardGame.objects.all())

        self.assertIn(game.pk, set(filtered.values_list("pk", flat=True)))

    def test_removed_copies_are_hidden_by_default_and_can_be_shown(self):
        active = BoardGameFactory(removed=False)
        removed = BoardGameFactory(removed=True)

        default_queryset = self.make_filter(ShowRemovedFilter).queryset(
            self.request,
            BoardGame.objects.all(),
        )
        show_removed_queryset = self.make_filter(
            ShowRemovedFilter,
            {"show_removed": "yes"},
        ).queryset(self.request, BoardGame.objects.all())

        self.assertEqual(
            set(default_queryset.values_list("pk", flat=True)), {active.pk}
        )
        self.assertEqual(
            set(show_removed_queryset.values_list("pk", flat=True)), {removed.pk}
        )

    def test_playing_time_filter_selects_ranges_and_unknown_values(self):
        games = {}
        for label, duration in (
            ("short", 30),
            ("medium", 45),
            ("long", 90),
            ("very_long", 180),
            ("unknown", None),
        ):
            metadata = BGGMetadataFactory(
                playingtime=duration,
                bgg_id=13100 + len(games),
            )
            games[label] = BoardGameFactory(metadata=metadata)

        expected = {
            "up_to_30": {games["short"].pk},
            "31_to_60": {games["medium"].pk},
            "61_to_120": {games["long"].pk},
            "over_120": {games["very_long"].pk},
            "unknown": {games["unknown"].pk},
        }
        for selected, expected_pks in expected.items():
            with self.subTest(selected=selected):
                filtered = self.make_filter(
                    PlayingTimeFilter,
                    {"bgg_playing_time": selected},
                ).queryset(self.request, BoardGame.objects.all())
                self.assertEqual(
                    set(filtered.values_list("pk", flat=True)), expected_pks
                )

    def test_official_player_count_filter_uses_bgg_min_and_max(self):
        ranges = {
            "solo": (1, 1),
            "one_to_four": (1, 4),
            "two_to_five": (2, 5),
            "five_to_eight": (5, 8),
            "up_to_four": (None, 4),
            "unknown_max": (2, None),
        }
        games = {}
        for index, (label, (minimum, maximum)) in enumerate(ranges.items()):
            metadata = BGGMetadataFactory(
                bgg_id=13200 + index,
                minplayers=minimum,
                maxplayers=maximum,
                suggested_players=(
                    {"numplayers": "2", "best": 100, "recommended": 100},
                ),
            )
            games[label] = BoardGameFactory(metadata=metadata)
        local_only = BoardGameFactory(metadata=None)

        expected = {
            "1": {games["solo"].pk, games["one_to_four"].pk},
            "2": {
                games["one_to_four"].pk,
                games["two_to_five"].pk,
            },
            "3": {games["one_to_four"].pk, games["two_to_five"].pk},
            "4": {
                games["one_to_four"].pk,
                games["two_to_five"].pk,
            },
            "5_plus": {
                games["two_to_five"].pk,
                games["five_to_eight"].pk,
            },
        }
        for selected, expected_pks in expected.items():
            with self.subTest(selected=selected):
                filtered = self.make_filter(
                    OfficialPlayerCountFilter,
                    {"official_players": selected},
                ).queryset(self.request, BoardGame.objects.all())
                self.assertEqual(
                    set(filtered.values_list("pk", flat=True)), expected_pks
                )
                self.assertNotIn(
                    local_only.pk, set(filtered.values_list("pk", flat=True))
                )

    def test_rank_filter_distinguishes_present_and_missing_rank(self):
        ranked = BGGMetadataFactory(bgg_id=13005, boardgame_rank=17)
        unranked = BGGMetadataFactory(bgg_id=13006, boardgame_rank=None)
        ranked_copy = BoardGameFactory(metadata=ranked)
        unranked_copy = BoardGameFactory(metadata=unranked)

        with_rank = self.make_filter(
            HasBGGRankFilter,
            {"has_bgg_rank": "yes"},
        ).queryset(self.request, BoardGame.objects.all())
        without_rank = self.make_filter(
            HasBGGRankFilter,
            {"has_bgg_rank": "no"},
        ).queryset(self.request, BoardGame.objects.all())

        self.assertEqual(set(with_rank.values_list("pk", flat=True)), {ranked_copy.pk})
        self.assertEqual(
            set(without_rank.values_list("pk", flat=True)), {unranked_copy.pk}
        )
