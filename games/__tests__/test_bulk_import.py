from datetime import date
from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase

from games.admin import GameAdmin
from games.admin_views.bulk_import import bulk_import_view, process_bulk_import
from games.api.__tests__.factories import (
    GameFactory,
    PlatformFactory,
    UserFactory,
    VendorFactory,
)
from games.forms import BulkGameImportForm, GameImportFormSet
from games.models import Game, GameOnPlatform


def add_messages_to_request(request):
    """Add messages framework to request for testing"""
    request.session = {}
    messages = FallbackStorage(request)
    request._messages = messages


class BulkGameImportAdminTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.admin = GameAdmin(Game, self.site)
        self.user = UserFactory()
        self.vendor = VendorFactory(name="Humble Bundle")
        self.platform_steam = PlatformFactory(name="Steam")
        self.platform_epic = PlatformFactory(name="Epic Games")

    def test_bulk_import_view_get_renders_form(self):
        """Test that GET request renders the bulk import form"""
        request = self.factory.get("/admin/games/game/bulk_import/")
        request.user = self.user

        response = self.admin.bulk_import_games(request)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bulk Import Games")
        self.assertContains(response, "Bundle Information")
        self.assertContains(response, "Quick Input")
        self.assertContains(response, "Individual Games")

    def test_bulk_import_creates_new_games(self):
        """Test bulk import creates new games with correct data"""
        request = self.factory.post(
            "/admin/games/game/bulk_import/",
            {
                "vendor": self.vendor.id,
                "bundle_date": "2024-01-15",
                "bundle_price": "29.99",
                "form-TOTAL_FORMS": "2",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-game_name": "New Game 1",
                "form-0-platform": self.platform_steam.id,
                "form-0-play_priority": "8",
                "form-1-game_name": "New Game 2",
                "form-1-platform": self.platform_epic.id,
                "form-1-play_priority": "5",
            },
        )
        request.user = self.user
        add_messages_to_request(request)

        self.admin.bulk_import_games(request)

        # Check games were created
        self.assertTrue(Game.objects.filter(name="New Game 1").exists())
        self.assertTrue(Game.objects.filter(name="New Game 2").exists())

        # Check GameOnPlatform entries with correct data
        game1 = Game.objects.get(name="New Game 1")
        game2 = Game.objects.get(name="New Game 2")

        gop1 = GameOnPlatform.objects.get(game=game1)
        gop2 = GameOnPlatform.objects.get(game=game2)

        # Price should be split evenly: 29.99 / 2 = 14.995 -> 15.00
        expected_price = Decimal("15.00")
        self.assertEqual(gop1.price, expected_price)
        self.assertEqual(gop2.price, expected_price)

        self.assertEqual(gop1.vendor, self.vendor)
        self.assertEqual(gop2.vendor, self.vendor)

        # Check play priorities
        self.assertEqual(game1.play_priority, 8)
        self.assertEqual(game2.play_priority, 5)

    def test_bulk_import_detects_duplicates(self):
        """Test that duplicate games are detected and excluded"""
        # Create existing game
        GameFactory(name="Existing Game")

        request = self.factory.post(
            "/admin/games/game/bulk_import/",
            {
                "vendor": self.vendor.id,
                "bundle_date": "2024-01-15",
                "bundle_price": "20.00",
                "form-TOTAL_FORMS": "2",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-game_name": "Existing Game",  # Duplicate
                "form-0-platform": self.platform_steam.id,
                "form-1-game_name": "New Game",
                "form-1-platform": self.platform_epic.id,
            },
        )
        request.user = self.user
        add_messages_to_request(request)

        self.admin.bulk_import_games(request)

        # Only one new game should be created
        new_games = Game.objects.filter(name="New Game")
        self.assertEqual(new_games.count(), 1)

        # Price should be the full bundle price (no split for duplicates)
        new_game = new_games.first()
        gop = GameOnPlatform.objects.get(game=new_game)
        self.assertEqual(gop.price, Decimal("20.00"))

    def test_bulk_import_global_platform_fallback(self):
        """Test that global platform works as fallback for games without specific platform"""
        request = self.factory.post(
            "/admin/games/game/bulk_import/",
            {
                "vendor": self.vendor.id,
                "bundle_date": "2024-01-15",
                "bundle_price": "30.00",
                "global_platform": self.platform_steam.id,  # Fallback platform
                "form-TOTAL_FORMS": "3",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-game_name": "Game with specific platform",
                "form-0-platform": self.platform_epic.id,  # Specific platform - should NOT be overridden
                "form-1-game_name": "Game without platform",
                "form-1-platform": "",  # No platform - should use fallback
                "form-2-game_name": "Another game without platform",
                "form-2-platform": "",  # No platform - should use fallback
            },
        )
        request.user = self.user
        add_messages_to_request(request)

        self.admin.bulk_import_games(request)

        # Game with specific platform should keep its Epic platform
        game1 = Game.objects.get(name="Game with specific platform")
        gop1 = GameOnPlatform.objects.get(game=game1)
        self.assertEqual(gop1.platform, self.platform_epic)

        # Games without platform should use Steam fallback
        game2 = Game.objects.get(name="Game without platform")
        gop2 = GameOnPlatform.objects.get(game=game2)
        self.assertEqual(gop2.platform, self.platform_steam)

        game3 = Game.objects.get(name="Another game without platform")
        gop3 = GameOnPlatform.objects.get(game=game3)
        self.assertEqual(gop3.platform, self.platform_steam)

    def test_bulk_import_quick_input_field(self):
        """Test quick input field for comma-separated games"""
        request = self.factory.post(
            "/admin/games/game/bulk_import/",
            {
                "vendor": self.vendor.id,
                "bundle_date": "2024-01-15",
                "bundle_price": "45.00",
                "global_platform": self.platform_steam.id,
                "quick_games": "Quick Game 1, Quick Game 2, Quick Game 3",
                "form-TOTAL_FORMS": "0",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
            },
        )
        request.user = self.user
        add_messages_to_request(request)

        self.admin.bulk_import_games(request)

        # All three games should be created
        self.assertTrue(Game.objects.filter(name="Quick Game 1").exists())
        self.assertTrue(Game.objects.filter(name="Quick Game 2").exists())
        self.assertTrue(Game.objects.filter(name="Quick Game 3").exists())

        # Price should be split evenly: 45.00 / 3 = 15.00
        for game_name in ["Quick Game 1", "Quick Game 2", "Quick Game 3"]:
            game = Game.objects.get(name=game_name)
            gop = GameOnPlatform.objects.get(game=game)
            self.assertEqual(gop.price, Decimal("15.00"))
            self.assertEqual(gop.platform, self.platform_steam)

    def test_bulk_import_mixed_quick_and_detailed(self):
        """Test combining quick input with detailed form entries"""
        request = self.factory.post(
            "/admin/games/game/bulk_import/",
            {
                "vendor": self.vendor.id,
                "bundle_date": "2024-01-15",
                "bundle_price": "60.00",
                "global_platform": self.platform_steam.id,
                "quick_games": "Quick Game 1, Quick Game 2",
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-game_name": "Detailed Game",
                "form-0-platform": self.platform_epic.id,  # This will be overridden by global platform
                "form-0-play_priority": "9",
            },
        )
        request.user = self.user
        add_messages_to_request(request)

        self.admin.bulk_import_games(request)

        # All games should be created
        self.assertEqual(Game.objects.count(), 3)

        # Price should be split evenly: 60.00 / 3 = 20.00
        # Quick games should use global platform, detailed game should use its specific platform
        for game_name in ["Quick Game 1", "Quick Game 2"]:
            game = Game.objects.get(name=game_name)
            gop = GameOnPlatform.objects.get(game=game)
            self.assertEqual(gop.price, Decimal("20.00"))
            self.assertEqual(gop.platform, self.platform_steam)  # From global_platform

        # Detailed game should keep its specific platform (Epic)
        detailed_game = Game.objects.get(name="Detailed Game")
        detailed_gop = GameOnPlatform.objects.get(game=detailed_game)
        self.assertEqual(detailed_gop.price, Decimal("20.00"))
        self.assertEqual(detailed_gop.platform, self.platform_epic)  # Specific platform

    def test_bulk_import_handles_empty_forms(self):
        """Test that empty form entries are ignored"""
        request = self.factory.post(
            "/admin/games/game/bulk_import/",
            {
                "vendor": self.vendor.id,
                "bundle_date": "2024-01-15",
                "bundle_price": "20.00",
                "form-TOTAL_FORMS": "3",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-game_name": "Valid Game",
                "form-0-platform": self.platform_steam.id,
                "form-1-game_name": "",  # Empty name
                "form-1-platform": self.platform_steam.id,
                "form-2-game_name": "Another Valid Game",
                "form-2-platform": self.platform_epic.id,
            },
        )
        request.user = self.user
        add_messages_to_request(request)

        self.admin.bulk_import_games(request)

        # Only 2 games should be created (empty form ignored)
        self.assertEqual(Game.objects.count(), 2)
        self.assertTrue(Game.objects.filter(name="Valid Game").exists())
        self.assertTrue(Game.objects.filter(name="Another Valid Game").exists())

        # Price should be split between 2 games: 20.00 / 2 = 10.00
        for game_name in ["Valid Game", "Another Valid Game"]:
            game = Game.objects.get(name=game_name)
            gop = GameOnPlatform.objects.get(game=game)
            self.assertEqual(gop.price, Decimal("10.00"))

    def test_bulk_import_validation_errors(self):
        """Test form validation for required fields"""
        request = self.factory.post(
            "/admin/games/game/bulk_import/",
            {
                # Missing required vendor
                "bundle_date": "2024-01-15",
                "bundle_price": "20.00",
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-game_name": "Test Game",
                "form-0-platform": self.platform_steam.id,
            },
        )
        request.user = self.user

        response = self.admin.bulk_import_games(request)

        # Form should have errors
        self.assertContains(response, "This field is required")
        # No games should be created
        self.assertEqual(Game.objects.count(), 0)

    def test_bulk_import_quick_games_requires_global_platform(self):
        """Test that quick games requires global platform override"""
        request = self.factory.post(
            "/admin/games/game/bulk_import/",
            {
                "vendor": self.vendor.id,
                "bundle_date": "2024-01-15",
                "bundle_price": "30.00",
                # No global_platform set
                "quick_games": "Quick Game 1, Quick Game 2",
                "form-TOTAL_FORMS": "0",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
            },
        )
        request.user = self.user

        response = self.admin.bulk_import_games(request)

        # Form should have validation error
        self.assertContains(
            response, "Default Platform is required when using quick games input"
        )
        # No games should be created
        self.assertEqual(Game.objects.count(), 0)

    def test_bulk_import_duplicate_exclusion_from_price_split(self):
        """Test that duplicates are properly excluded from price calculations"""
        # Create existing games
        GameFactory(name="Existing Game 1")
        GameFactory(name="Existing Game 2")

        request = self.factory.post(
            "/admin/games/game/bulk_import/",
            {
                "vendor": self.vendor.id,
                "bundle_date": "2024-01-15",
                "bundle_price": "30.00",
                "form-TOTAL_FORMS": "4",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-game_name": "Existing Game 1",  # Duplicate
                "form-0-platform": self.platform_steam.id,
                "form-1-game_name": "Existing Game 2",  # Duplicate
                "form-1-platform": self.platform_steam.id,
                "form-2-game_name": "New Game 1",
                "form-2-platform": self.platform_steam.id,
                "form-3-game_name": "New Game 2",
                "form-3-platform": self.platform_epic.id,
            },
        )
        request.user = self.user
        add_messages_to_request(request)

        self.admin.bulk_import_games(request)

        # Only 2 new games should be created
        new_game1 = Game.objects.get(name="New Game 1")
        new_game2 = Game.objects.get(name="New Game 2")

        # Price should be split only between new games: 30.00 / 2 = 15.00
        gop1 = GameOnPlatform.objects.get(game=new_game1)
        gop2 = GameOnPlatform.objects.get(game=new_game2)

        self.assertEqual(gop1.price, Decimal("15.00"))
        self.assertEqual(gop2.price, Decimal("15.00"))

    def test_bulk_import_form_has_current_date_as_default(self):
        """Test that the bundle date field defaults to current date"""
        request = self.factory.get("/admin/games/game/bulk_import/")
        request.user = self.user

        response = self.admin.bulk_import_games(request)

        # Check that the form contains today's date as default
        self.assertEqual(response.status_code, 200)
        today = date.today().isoformat()
        self.assertContains(response, f'value="{today}"')

    def test_bulk_import_free_bundle_price_zero(self):
        """Test that free bundles (price = 0) work correctly"""
        request = self.factory.post(
            "/admin/games/game/bulk_import/",
            {
                "vendor": self.vendor.id,
                "bundle_date": "2024-01-15",
                "bundle_price": "0.00",  # Free bundle
                "global_platform": self.platform_steam.id,
                "quick_games": "Free Game 1, Free Game 2",
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-game_name": "Another Free Game",
                "form-0-platform": self.platform_steam.id,
            },
        )
        request.user = self.user
        add_messages_to_request(request)

        self.admin.bulk_import_games(request)

        # All games should be created
        self.assertTrue(Game.objects.filter(name="Free Game 1").exists())
        self.assertTrue(Game.objects.filter(name="Free Game 2").exists())
        self.assertTrue(Game.objects.filter(name="Another Free Game").exists())

        # All games should have price = 0.00
        for game_name in ["Free Game 1", "Free Game 2", "Another Free Game"]:
            game = Game.objects.get(name=game_name)
            gop = GameOnPlatform.objects.get(game=game)
            self.assertEqual(gop.price, Decimal("0.00"))
            self.assertEqual(gop.platform, self.platform_steam)

    def test_bulk_import_form_has_default_date(self):
        """Test that the bulk import form initializes with today's date"""

        form = BulkGameImportForm()

        # Form should have today as the initial value (function reference)
        self.assertEqual(form.fields["bundle_date"].initial, date.today)

        # Unbound form should show today's date in rendered HTML
        rendered_html = str(form["bundle_date"])
        self.assertIn(f'value="{date.today().isoformat()}"', rendered_html)
        self.assertIn('type="date"', rendered_html)


class BulkImportViewTestCase(TestCase):
    """Test standalone bulk import view functions (TDD for refactored code)"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()
        self.vendor = VendorFactory(name="Test Vendor")
        self.platform_steam = PlatformFactory(name="Steam")
        self.platform_epic = PlatformFactory(name="Epic Games")

    def test_bulk_import_view_get_renders_form(self):
        """Test that GET request renders the bulk import form"""
        request = self.factory.get("/admin/games/game/bulk_import/")
        request.user = self.user

        response = bulk_import_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bulk Import Games")
        self.assertContains(response, "Bundle Information")
        self.assertContains(response, "Quick Input")
        self.assertContains(response, "Individual Games")

    def test_bulk_import_view_post_valid_data(self):
        """Test POST with valid form data calls process function"""
        request = self.factory.post(
            "/admin/games/game/bulk_import/",
            {
                "vendor": self.vendor.id,
                "bundle_date": "2024-01-15",
                "bundle_price": "25.99",
                "global_platform": self.platform_steam.id,
                "quick_games": "Test Game 1, Test Game 2",
                "form-TOTAL_FORMS": "0",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
            },
        )
        request.user = self.user
        add_messages_to_request(request)

        response = bulk_import_view(request)

        # Should redirect after successful processing
        self.assertEqual(response.status_code, 302)

        # Verify games were created
        self.assertTrue(Game.objects.filter(name="Test Game 1").exists())
        self.assertTrue(Game.objects.filter(name="Test Game 2").exists())

    def test_bulk_import_view_post_invalid_data(self):
        """Test POST with invalid data re-renders form with errors"""
        request = self.factory.post(
            "/admin/games/game/bulk_import/",
            {
                # Missing required vendor field
                "bundle_date": "2024-01-15",
                "bundle_price": "25.99",
                "form-TOTAL_FORMS": "0",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
            },
        )
        request.user = self.user

        response = bulk_import_view(request)

        # Should re-render form with errors
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")

        # No games should be created
        self.assertEqual(Game.objects.count(), 0)

    def test_process_bulk_import_creates_games_from_quick_input(self):
        """Test process_bulk_import creates games from quick input field"""
        form_data = {
            "vendor": self.vendor.id,
            "bundle_date": "2024-01-15",
            "bundle_price": "30.00",
            "global_platform": self.platform_steam.id,
            "quick_games": "Quick Game 1, Quick Game 2",
        }

        form = BulkGameImportForm(form_data)
        formset = GameImportFormSet(
            {
                "form-TOTAL_FORMS": "0",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
            }
        )

        self.assertTrue(form.is_valid())
        self.assertTrue(formset.is_valid())

        request = self.factory.post("/")
        request.user = self.user
        add_messages_to_request(request)

        response = process_bulk_import(request, form, formset)

        # Should redirect after success
        self.assertEqual(response.status_code, 302)

        # Verify games were created
        game1 = Game.objects.get(name="Quick Game 1")
        game2 = Game.objects.get(name="Quick Game 2")

        # Verify platform relationships
        gop1 = GameOnPlatform.objects.get(game=game1)
        gop2 = GameOnPlatform.objects.get(game=game2)

        self.assertEqual(gop1.platform, self.platform_steam)
        self.assertEqual(gop1.vendor, self.vendor)
        self.assertEqual(gop1.price, Decimal("15.00"))  # 30.00 / 2 games

        self.assertEqual(gop2.platform, self.platform_steam)
        self.assertEqual(gop2.vendor, self.vendor)
        self.assertEqual(gop2.price, Decimal("15.00"))

    def test_process_bulk_import_creates_games_from_formset(self):
        """Test process_bulk_import creates games from detailed formset"""

        form_data = {
            "vendor": self.vendor.id,
            "bundle_date": "2024-01-15",
            "bundle_price": "25.00",
            "global_platform": "",  # No global platform
        }

        formset_data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-game_name": "Formset Game 1",
            "form-0-platform": self.platform_steam.id,
            "form-0-play_priority": "8",
            "form-1-game_name": "Formset Game 2",
            "form-1-platform": self.platform_epic.id,
            "form-1-play_priority": "5",
        }

        form = BulkGameImportForm(form_data)
        formset = GameImportFormSet(formset_data)

        self.assertTrue(form.is_valid())
        self.assertTrue(formset.is_valid())

        request = self.factory.post("/")
        request.user = self.user
        add_messages_to_request(request)

        response = process_bulk_import(request, form, formset)

        # Should redirect after success
        self.assertEqual(response.status_code, 302)

        # Verify games were created with correct attributes
        game1 = Game.objects.get(name="Formset Game 1")
        game2 = Game.objects.get(name="Formset Game 2")

        self.assertEqual(game1.play_priority, 8)
        self.assertEqual(game2.play_priority, 5)

        # Verify platform relationships
        gop1 = GameOnPlatform.objects.get(game=game1)
        gop2 = GameOnPlatform.objects.get(game=game2)

        self.assertEqual(gop1.platform, self.platform_steam)
        self.assertEqual(gop2.platform, self.platform_epic)
        self.assertEqual(gop1.price, Decimal("12.50"))  # 25.00 / 2 games
        self.assertEqual(gop2.price, Decimal("12.50"))

    def test_process_bulk_import_handles_duplicates(self):
        """Test process_bulk_import properly handles duplicate games"""

        # Create existing game
        GameFactory(name="Existing Game")

        form_data = {
            "vendor": self.vendor.id,
            "bundle_date": "2024-01-15",
            "bundle_price": "20.00",
            "global_platform": self.platform_steam.id,
            "quick_games": "Existing Game, New Game",
        }

        form = BulkGameImportForm(form_data)
        formset = GameImportFormSet(
            {
                "form-TOTAL_FORMS": "0",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
            }
        )

        self.assertTrue(form.is_valid())
        self.assertTrue(formset.is_valid())

        request = self.factory.post("/")
        request.user = self.user
        add_messages_to_request(request)

        response = process_bulk_import(request, form, formset)

        # Should redirect after success
        self.assertEqual(response.status_code, 302)

        # Only new game should be created
        self.assertEqual(
            Game.objects.filter(name="Existing Game").count(), 1
        )  # Still just 1
        self.assertTrue(Game.objects.filter(name="New Game").exists())

        # New game should get full price (not split with duplicate)
        new_game = Game.objects.get(name="New Game")
        gop = GameOnPlatform.objects.get(game=new_game)
        self.assertEqual(gop.price, Decimal("20.00"))  # Full price, not split

    def test_process_bulk_import_mixed_input_sources(self):
        """Test process_bulk_import handles both quick input and formset"""

        form_data = {
            "vendor": self.vendor.id,
            "bundle_date": "2024-01-15",
            "bundle_price": "40.00",
            "global_platform": self.platform_steam.id,
            "quick_games": "Quick Game 1, Quick Game 2",
        }

        formset_data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-game_name": "Detailed Game",
            "form-0-platform": self.platform_epic.id,  # Different platform
            "form-0-play_priority": "9",
        }

        form = BulkGameImportForm(form_data)
        formset = GameImportFormSet(formset_data, global_platform=self.platform_steam)

        self.assertTrue(form.is_valid())
        self.assertTrue(formset.is_valid())

        request = self.factory.post("/")
        request.user = self.user
        add_messages_to_request(request)

        response = process_bulk_import(request, form, formset)

        # Should redirect after success
        self.assertEqual(response.status_code, 302)

        # All 3 games should be created
        self.assertEqual(Game.objects.count(), 3)

        # Verify platform assignments
        quick_game1 = Game.objects.get(name="Quick Game 1")
        quick_game2 = Game.objects.get(name="Quick Game 2")
        detailed_game = Game.objects.get(name="Detailed Game")

        # Quick games use global platform
        self.assertEqual(
            GameOnPlatform.objects.get(game=quick_game1).platform, self.platform_steam
        )
        self.assertEqual(
            GameOnPlatform.objects.get(game=quick_game2).platform, self.platform_steam
        )

        # Detailed game uses its specific platform
        self.assertEqual(
            GameOnPlatform.objects.get(game=detailed_game).platform, self.platform_epic
        )

        # Price should be split equally across all 3 games
        for game in [quick_game1, quick_game2, detailed_game]:
            gop = GameOnPlatform.objects.get(game=game)
            self.assertEqual(gop.price, Decimal("13.33"))  # 40.00 / 3 games

    def test_process_bulk_import_free_bundle(self):
        """Test process_bulk_import handles free bundles (price = 0)"""

        form_data = {
            "vendor": self.vendor.id,
            "bundle_date": "2024-01-15",
            "bundle_price": "0.00",  # Free bundle
            "global_platform": self.platform_steam.id,
            "quick_games": "Free Game 1, Free Game 2",
        }

        form = BulkGameImportForm(form_data)
        formset = GameImportFormSet(
            {
                "form-TOTAL_FORMS": "0",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
            }
        )

        self.assertTrue(form.is_valid())
        self.assertTrue(formset.is_valid())

        request = self.factory.post("/")
        request.user = self.user
        add_messages_to_request(request)

        response = process_bulk_import(request, form, formset)

        # Should redirect after success
        self.assertEqual(response.status_code, 302)

        # Verify games created with zero price
        for game_name in ["Free Game 1", "Free Game 2"]:
            game = Game.objects.get(name=game_name)
            gop = GameOnPlatform.objects.get(game=game)
            self.assertEqual(gop.price, Decimal("0.00"))

    def test_process_bulk_import_no_new_games_warning(self):
        """Test process_bulk_import shows warning when all games are duplicates"""

        # Create existing games
        GameFactory(name="Game 1")
        GameFactory(name="Game 2")

        form_data = {
            "vendor": self.vendor.id,
            "bundle_date": "2024-01-15",
            "bundle_price": "30.00",
            "global_platform": self.platform_steam.id,
            "quick_games": "Game 1, Game 2",  # All duplicates
        }

        form = BulkGameImportForm(form_data)
        formset = GameImportFormSet(
            {
                "form-TOTAL_FORMS": "0",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
            }
        )

        self.assertTrue(form.is_valid())
        self.assertTrue(formset.is_valid())

        request = self.factory.post("/")
        request.user = self.user
        add_messages_to_request(request)

        response = process_bulk_import(request, form, formset)

        # Should still redirect
        self.assertEqual(response.status_code, 302)

        # No new games should be created
        self.assertEqual(Game.objects.count(), 2)  # Only the existing ones

    def test_bulk_import_view_form_has_default_date(self):
        """Test that GET request renders form with today's date as default"""

        request = self.factory.get("/admin/games/game/bulk_import/")
        request.user = self.user

        response = bulk_import_view(request)

        self.assertEqual(response.status_code, 200)
        # Check that the form contains today's date as default
        today = date.today().isoformat()
        self.assertContains(response, f'value="{today}"')
