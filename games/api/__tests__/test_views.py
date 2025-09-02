from uuid import uuid4

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from ...models import GameOnPlatform, Platform, Vendor
from .factories import GameFactory, PlatformFactory, UserFactory, VendorFactory


class GameAPITestCase(APITestCase):
    def setUp(self):
        # Create a staff user for authentication
        self.staff_user = UserFactory()

        # Create test platforms and vendors
        self.platform1 = PlatformFactory(name="PC")
        self.platform2 = PlatformFactory(name="PlayStation 5")
        self.vendor1 = VendorFactory(name="Steam")
        self.vendor2 = VendorFactory(name="Epic Games Store")

        # Create test games
        self.game1 = GameFactory(
            name="The Witcher 3",
            play_priority=9,
            played=False,
            controller_support=True,
            max_players=1,
        )

        self.game2 = GameFactory(
            name="Cyberpunk 2077",
            play_priority=8,
            played=True,
            controller_support=True,
            max_players=1,
        )

        self.game3 = GameFactory(
            name="Portal 2",
            play_priority=10,
            played=True,
            controller_support=False,
            max_players=2,
        )

    def _get_auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {settings.API_TOKEN}"}

    def test_game_list_without_auth_fails(self):
        url = reverse("game-list-create-api")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_game_detail_without_auth_fails(self):
        url = reverse("game-detail-api", kwargs={"id": self.game1.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class GameListCreateAPIViewTestCase(GameAPITestCase):
    def test_game_list_with_auth_succeeds(self):
        url = reverse("game-list-create-api")
        response = self.client.get(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

    def test_game_list_search_by_name(self):
        url = reverse("game-list-create-api")
        response = self.client.get(
            url, {"search": "witcher"}, **self._get_auth_headers()
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "The Witcher 3")

    def test_game_list_search_case_insensitive(self):
        url = reverse("game-list-create-api")
        response = self.client.get(
            url, {"search": "PORTAL"}, **self._get_auth_headers()
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Portal 2")

    def test_game_list_search_partial_match(self):
        url = reverse("game-list-create-api")
        response = self.client.get(url, {"search": "cyber"}, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Cyberpunk 2077")

    def test_game_list_search_no_results(self):
        url = reverse("game-list-create-api")
        response = self.client.get(
            url, {"search": "nonexistent"}, **self._get_auth_headers()
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_create_game_with_all_required_fields(self):
        url = reverse("game-list-create-api")
        data = {
            "name": "New Game",
            "platform_name": "PC",
            "vendor_name": "Steam",
            "price": "29.99",
            "added": "2023-01-01",
        }
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "New Game")

    def test_create_game_without_date_uses_current_date(self):
        url = reverse("game-list-create-api")
        data = {
            "name": "Another Game",
            "platform_name": "PC",
            "vendor_name": "Steam",
            "price": "39.99",
        }
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        game_on_platform = GameOnPlatform.objects.get(game__name="Another Game")
        self.assertEqual(game_on_platform.added, timezone.now().date())

    def test_create_game_without_required_fields_fails(self):
        url = reverse("game-list-create-api")
        data = {"name": "Incomplete Game"}
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("platform_name", response.data)
        self.assertIn("vendor_name", response.data)
        self.assertIn("price", response.data)

    def test_create_game_trims_name_whitespace(self):
        url = reverse("game-list-create-api")
        data = {
            "name": "  Trimmed Game  ",
            "platform_name": "PC",
            "vendor_name": "Steam",
            "price": "29.99",
        }
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Trimmed Game")

    def test_create_game_trims_notes_whitespace(self):
        url = reverse("game-list-create-api")
        data = {
            "name": "Notes Game",
            "platform_name": "PC",
            "vendor_name": "Steam",
            "price": "29.99",
            "notes": "  These are some notes  ",
        }
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["notes"], "These are some notes")

    def test_create_game_with_new_platform_and_vendor(self):
        url = reverse("game-list-create-api")
        new_platform = PlatformFactory.build()
        new_vendor = VendorFactory.build()
        data = {
            "name": "New Platform Game",
            "platform_name": new_platform.name,
            "vendor_name": new_vendor.name,
            "price": "59.99",
        }
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify platform and vendor were created
        self.assertTrue(Platform.objects.filter(name=new_platform.name).exists())
        self.assertTrue(Vendor.objects.filter(name=new_vendor.name).exists())

    def test_create_game_trims_platform_and_vendor_names(self):
        url = reverse("game-list-create-api")
        platform_name = PlatformFactory.build().name
        vendor_name = VendorFactory.build().name
        data = {
            "name": "Trim Test Game",
            "platform_name": f"  {platform_name}  ",
            "vendor_name": f"  {vendor_name}  ",
            "price": "49.99",
        }
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify trimmed names were used
        self.assertTrue(Platform.objects.filter(name=platform_name).exists())
        self.assertTrue(Vendor.objects.filter(name=vendor_name).exists())
        self.assertFalse(Platform.objects.filter(name=f"  {platform_name}  ").exists())
        self.assertFalse(Vendor.objects.filter(name=f"  {vendor_name}  ").exists())

    def test_create_game_reuses_existing_platform_and_vendor(self):
        url = reverse("game-list-create-api")

        # Use unique names from factories
        platform_name = PlatformFactory.build().name
        vendor_name = VendorFactory.build().name

        # Create first game with new platform/vendor
        data1 = {
            "name": "First Game",
            "platform_name": platform_name,
            "vendor_name": vendor_name,
            "price": "69.99",
        }
        response1 = self.client.post(url, data1, **self._get_auth_headers())
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        platform_count = Platform.objects.filter(name=platform_name).count()
        vendor_count = Vendor.objects.filter(name=vendor_name).count()

        # Create second game with same platform/vendor
        data2 = {
            "name": "Second Game",
            "platform_name": platform_name,
            "vendor_name": vendor_name,
            "price": "79.99",
        }
        response2 = self.client.post(url, data2, **self._get_auth_headers())
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)

        # Verify no duplicates were created
        self.assertEqual(
            Platform.objects.filter(name=platform_name).count(), platform_count
        )
        self.assertEqual(Vendor.objects.filter(name=vendor_name).count(), vendor_count)

    def test_create_game_case_insensitive_platform_matching(self):
        # Create a platform with specific casing
        platform = PlatformFactory(name="Nintendo Switch")
        vendor_name = VendorFactory.build().name

        url = reverse("game-list-create-api")
        data = {
            "name": "Case Test Game",
            "platform_name": "nintendo switch",  # lowercase
            "vendor_name": vendor_name,
            "price": "29.99",
        }
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Should only have one Nintendo Switch platform (the original casing)
        platforms = Platform.objects.filter(name__iexact="nintendo switch")
        self.assertEqual(platforms.count(), 1)
        self.assertEqual(
            platforms.first().name, platform.name
        )  # Original casing preserved

    def test_create_game_case_insensitive_vendor_matching(self):
        # Create a vendor with specific casing
        vendor = VendorFactory(name="GOG Galaxy")
        platform_name = PlatformFactory.build().name

        url = reverse("game-list-create-api")
        data = {
            "name": "Vendor Case Test",
            "platform_name": platform_name,
            "vendor_name": "GOG GALAXY",  # uppercase
            "price": "19.99",
        }
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Should only have one GOG Galaxy vendor (the original casing)
        vendors = Vendor.objects.filter(name__iexact="gog galaxy")
        self.assertEqual(vendors.count(), 1)
        self.assertEqual(vendors.first().name, vendor.name)  # Original casing preserved

    def test_create_game_preserves_new_platform_casing(self):
        url = reverse("game-list-create-api")
        vendor_name = VendorFactory.build().name
        data = {
            "name": "New Casing Test",
            "platform_name": "Nintendo Switch OLED",  # Specific casing
            "vendor_name": vendor_name,
            "price": "39.99",
        }
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Should preserve the exact casing provided
        platform = Platform.objects.get(name__iexact="nintendo switch oled")
        self.assertEqual(platform.name, "Nintendo Switch OLED")

    def test_create_game_preserves_new_vendor_casing(self):
        url = reverse("game-list-create-api")
        platform_name = PlatformFactory.build().name
        data = {
            "name": "Vendor Casing Test",
            "platform_name": platform_name,
            "vendor_name": "GOG.com",  # Specific casing with dots
            "price": "14.99",
        }
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Should preserve the exact casing provided
        vendor = Vendor.objects.get(name__iexact="gog.com")
        self.assertEqual(vendor.name, "GOG.com")

    def test_create_game_mixed_case_scenarios(self):
        # Pre-create some entries with specific casing
        platform = PlatformFactory(name="Xbox Series X")
        vendor = VendorFactory(name="Microsoft Store")

        url = reverse("game-list-create-api")

        # Test various case combinations
        test_cases = [
            ("xbox series x", "microsoft store"),
            ("XBOX SERIES X", "MICROSOFT STORE"),
            ("Xbox SERIES x", "Microsoft STORE"),
        ]

        for i, (platform_name, vendor_name) in enumerate(test_cases):
            with self.subTest(case=i):
                data = {
                    "name": f"Mixed Case Game {i}",
                    "platform_name": platform_name,
                    "vendor_name": vendor_name,
                    "price": "29.99",
                }
                response = self.client.post(url, data, **self._get_auth_headers())
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Should still only have one of each with original casing
        self.assertEqual(
            Platform.objects.filter(name__iexact="xbox series x").count(), 1
        )
        self.assertEqual(
            Vendor.objects.filter(name__iexact="microsoft store").count(), 1
        )

        platform = Platform.objects.get(name__iexact="xbox series x")
        vendor = Vendor.objects.get(name__iexact="microsoft store")
        self.assertEqual(platform.name, "Xbox Series X")
        self.assertEqual(vendor.name, "Microsoft Store")


class GameDetailAPIViewTestCase(GameAPITestCase):
    def test_game_detail_with_auth_succeeds(self):
        """Test that authenticated requests to detail endpoint work"""
        url = reverse("game-detail-api", kwargs={"id": self.game1.id})
        response = self.client.get(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.game1.id))
        self.assertEqual(response.data["name"], "The Witcher 3")

    def test_game_detail_includes_all_fields(self):
        """Test that detail response includes all expected fields"""
        url = reverse("game-detail-api", kwargs={"id": self.game1.id})
        response = self.client.get(url, **self._get_auth_headers())

        expected_fields = [
            "id",
            "name",
            "play_priority",
            "played",
            "controller_support",
            "max_players",
            "party_fit",
            "review",
            "notes",
            "genres",
            "platforms_meta_data",
        ]

        for field in expected_fields:
            self.assertIn(field, response.data)

    def test_game_detail_nonexistent_returns_404(self):
        """Test that requesting nonexistent game returns 404"""

        nonexistent_id = uuid4()
        url = reverse("game-detail-api", kwargs={"id": nonexistent_id})
        response = self.client.get(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class APITokenAuthenticationTestCase(GameAPITestCase):
    def test_auth_with_bearer_token(self):
        url = reverse("game-list-create-api")
        response = self.client.get(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_auth_with_url_parameter(self):
        url = reverse("game-list-create-api")
        response = self.client.get(url, {"api_token": settings.API_TOKEN})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_auth_with_invalid_token_fails(self):
        url = reverse("game-list-create-api")
        response = self.client.get(url, HTTP_AUTHORIZATION="Bearer invalid-token")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_auth_with_wrong_token_type_fails(self):
        url = reverse("game-list-create-api")
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Token {settings.API_TOKEN}"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PlatformListCreateAPIViewTestCase(GameAPITestCase):
    def test_create_platform_success(self):
        url = reverse("platform-list-create-api")
        data = {"name": "New Platform"}
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "New Platform")
        self.assertTrue(Platform.objects.filter(name="New Platform").exists())

    def test_create_platform_trims_whitespace(self):
        url = reverse("platform-list-create-api")
        data = {"name": "  Trimmed Platform  "}
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Trimmed Platform")

    def test_create_platform_without_name_fails(self):
        url = reverse("platform-list-create-api")
        data = {}
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)


class GamePlatformCreateAPIViewTestCase(GameAPITestCase):
    def setUp(self):
        super().setUp()
        # Add a platform to game1 for testing
        GameOnPlatform.objects.create(
            game=self.game1, platform=self.platform1, source=self.vendor1, price=29.99
        )

    def test_add_platform_to_game_success(self):
        url = reverse("game-platform-create-api", kwargs={"game_id": self.game1.id})
        data = {
            "platform_name": "PlayStation 5",
            "vendor_name": "PlayStation Store",
            "price": "59.99",
            "identifier": "PS5-123",
        }
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify GameOnPlatform was created
        game_platform = GameOnPlatform.objects.get(
            game=self.game1, platform__name="PlayStation 5"
        )
        self.assertEqual(str(game_platform.price), "59.99")
        self.assertEqual(game_platform.identifier, "PS5-123")

    def test_add_platform_minimal_data(self):
        url = reverse("game-platform-create-api", kwargs={"game_id": self.game1.id})
        data = {"platform_name": "Nintendo Switch"}
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_add_duplicate_platform_fails(self):
        url = reverse("game-platform-create-api", kwargs={"game_id": self.game1.id})
        data = {"platform_name": "PC"}  # Already exists for game1
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("This game already exists on this platform", str(response.data))

    def test_add_platform_nonexistent_game_fails(self):
        nonexistent_id = uuid4()
        url = reverse("game-platform-create-api", kwargs={"game_id": nonexistent_id})
        data = {"platform_name": "PC"}
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class GamePlatformDetailAPIViewTestCase(GameAPITestCase):
    def setUp(self):
        super().setUp()
        # Create GameOnPlatform relationship for testing
        self.game_platform = GameOnPlatform.objects.create(
            game=self.game1,
            platform=self.platform1,
            source=self.vendor1,
            price=29.99,
            identifier="PC-123",
        )

    def test_update_game_platform_patch(self):
        url = reverse(
            "game-platform-detail-api",
            kwargs={"game_id": self.game1.id, "platform_id": self.platform1.id},
        )
        data = {"price": "39.99", "vendor_name": "Epic Games Store"}
        response = self.client.patch(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.game_platform.refresh_from_db()
        self.assertEqual(str(self.game_platform.price), "39.99")
        self.assertEqual(self.game_platform.source.name, "Epic Games Store")

    def test_update_game_platform_put(self):
        url = reverse(
            "game-platform-detail-api",
            kwargs={"game_id": self.game1.id, "platform_id": self.platform1.id},
        )
        data = {"price": "49.99", "identifier": "PC-456", "vendor_name": "GOG"}
        response = self.client.put(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.game_platform.refresh_from_db()
        self.assertEqual(str(self.game_platform.price), "49.99")
        self.assertEqual(self.game_platform.identifier, "PC-456")

    def test_delete_game_platform(self):
        url = reverse(
            "game-platform-detail-api",
            kwargs={"game_id": self.game1.id, "platform_id": self.platform1.id},
        )
        response = self.client.delete(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify relationship was soft deleted (still exists but marked as deleted)
        game_platform = GameOnPlatform.objects.get(
            game=self.game1, platform=self.platform1
        )
        self.assertTrue(game_platform.deleted)
        self.assertIsNotNone(game_platform.deleted_at)

        # Verify it's not accessible via API anymore (filtered out by deleted=False)
        self.assertFalse(
            GameOnPlatform.objects.filter(
                game=self.game1, platform=self.platform1, deleted=False
            ).exists()
        )

    def test_update_nonexistent_relationship_fails(self):
        url = reverse(
            "game-platform-detail-api",
            kwargs={
                "game_id": self.game1.id,
                "platform_id": self.platform2.id,  # Not associated with game1
            },
        )
        data = {"price": "19.99"}
        response = self.client.patch(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class GameUpdateAPIViewTestCase(GameAPITestCase):
    def test_update_game_patch(self):
        url = reverse("game-detail-api", kwargs={"id": self.game1.id})
        data = {"name": "The Witcher 3: Wild Hunt", "play_priority": 10, "played": True}
        response = self.client.patch(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.game1.refresh_from_db()
        self.assertEqual(self.game1.name, "The Witcher 3: Wild Hunt")
        self.assertEqual(self.game1.play_priority, 10)
        self.assertTrue(self.game1.played)

    def test_update_game_put(self):
        url = reverse("game-detail-api", kwargs={"id": self.game1.id})
        data = {
            "name": "Updated Game Name",
            "play_priority": 5,
            "played": False,
            "controller_support": False,
            "max_players": 4,
            "party_fit": True,
            "review": 8,
            "notes": "Updated notes",
        }
        response = self.client.put(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.game1.refresh_from_db()
        self.assertEqual(self.game1.name, "Updated Game Name")
        self.assertEqual(self.game1.play_priority, 5)
        self.assertFalse(self.game1.played)

    def test_update_game_trims_whitespace(self):
        url = reverse("game-detail-api", kwargs={"id": self.game1.id})
        data = {"name": "  Trimmed Name  ", "notes": "  Trimmed Notes  "}
        response = self.client.patch(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.game1.refresh_from_db()
        self.assertEqual(self.game1.name, "Trimmed Name")
        self.assertEqual(self.game1.notes, "Trimmed Notes")

    def test_update_nonexistent_game_fails(self):
        nonexistent_id = uuid4()
        url = reverse("game-detail-api", kwargs={"id": nonexistent_id})
        data = {"name": "Should Fail"}
        response = self.client.patch(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class GamePlatformSoftDeleteTestCase(GameAPITestCase):
    def setUp(self):
        # Create a staff user for authentication
        self.staff_user = UserFactory()

        # Create test platforms and vendors
        self.platform1 = PlatformFactory(name="PC")
        self.platform2 = PlatformFactory(name="PlayStation 5")
        self.vendor1 = VendorFactory(name="Steam")
        self.vendor2 = VendorFactory(name="Epic Games Store")

        # Create test games WITHOUT default platforms (platforms=False)
        self.game1 = GameFactory(
            name="The Witcher 3",
            play_priority=9,
            played=False,
            controller_support=True,
            max_players=1,
            platforms=False,  # Don't create default platform
        )

        self.game2 = GameFactory(
            name="Cyberpunk 2077",
            play_priority=8,
            played=True,
            controller_support=True,
            max_players=1,
            platforms=False,  # Don't create default platform
        )

        self.game3 = GameFactory(
            name="Portal 2",
            play_priority=10,
            played=True,
            controller_support=False,
            max_players=2,
            platforms=False,  # Don't create default platform
        )

        # Create game-platform relationships for testing
        self.game1_platform1 = GameOnPlatform.objects.create(
            game=self.game1,
            platform=self.platform1,
            source=self.vendor1,
            price=29.99,
            identifier="PC-123",
        )
        self.game1_platform2 = GameOnPlatform.objects.create(
            game=self.game1,
            platform=self.platform2,
            source=self.vendor2,
            price=59.99,
            identifier="PS5-456",
        )

    def test_delete_platform_relationship_soft_delete(self):
        """Test that DELETE on game-platform relationship soft deletes it"""
        url = reverse(
            "game-platform-detail-api",
            kwargs={"game_id": self.game1.id, "platform_id": self.platform1.id},
        )
        response = self.client.delete(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # GameOnPlatform should still exist but be marked as deleted
        self.game1_platform1.refresh_from_db()
        self.assertTrue(self.game1_platform1.deleted)
        self.assertIsNotNone(self.game1_platform1.deleted_at)

    def test_game_with_deleted_platforms_excluded_from_list(self):
        """Test that games with all platforms deleted are excluded from game list"""
        # Initially should have 3 games
        url = reverse("game-list-create-api")
        response = self.client.get(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        initial_count = len(response.data)

        # Soft delete all platforms for game1
        self.game1_platform1.soft_delete()
        self.game1_platform2.soft_delete()

        # Now should have one less game
        response = self.client.get(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), initial_count - 1)

        # Verify the orphaned game is not in the results
        game_ids = [game["id"] for game in response.data]
        self.assertNotIn(str(self.game1.id), game_ids)

    def test_orphaned_game_returns_404_on_detail(self):
        """Test that GET on orphaned game (all platforms deleted) returns 404"""
        # Soft delete all platforms for game1
        self.game1_platform1.soft_delete()
        self.game1_platform2.soft_delete()

        url = reverse("game-detail-api", kwargs={"id": self.game1.id})
        response = self.client.get(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_game_with_some_active_platforms_still_visible(self):
        """Test that game with some active platforms is still visible"""
        # Soft delete one platform but not the other
        self.game1_platform1.soft_delete()

        # Game should still be visible in list
        url = reverse("game-list-create-api")
        response = self.client.get(url, **self._get_auth_headers())
        game_ids = [game["id"] for game in response.data]
        self.assertIn(str(self.game1.id), game_ids)

        # Game detail should still work
        url = reverse("game-detail-api", kwargs={"id": self.game1.id})
        response = self.client.get(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_nonexistent_platform_relationship(self):
        """Test DELETE on nonexistent game-platform relationship returns 404"""
        # Use platform not associated with game1
        url = reverse(
            "game-platform-detail-api",
            kwargs={
                "game_id": self.game1.id,
                "platform_id": 9999,  # Doesn't exist
            },
        )
        response = self.client.delete(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_already_deleted_platform_relationship(self):
        """Test DELETE on already deleted platform relationship returns 404"""
        # First soft delete the relationship
        self.game1_platform1.soft_delete()

        # Try to delete again
        url = reverse(
            "game-platform-detail-api",
            kwargs={"game_id": self.game1.id, "platform_id": self.platform1.id},
        )
        response = self.client.delete(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
