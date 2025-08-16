from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from decimal import Decimal
from uuid import uuid4

from ...models import Game, Platform, Vendor, GameOnPlatform


class GameAPITestCase(APITestCase):
    def setUp(self):
        # Create a staff user for authentication
        self.staff_user = User.objects.create_user(
            username="teststaff",
            email="test@example.com",
            password="testpass",
            is_staff=True,
            is_active=True,
        )

        # Create test platforms and vendors
        self.platform1 = Platform.objects.create(name="PC")
        self.platform2 = Platform.objects.create(name="PlayStation 5")
        self.vendor1 = Vendor.objects.create(name="Steam")
        self.vendor2 = Vendor.objects.create(name="Epic Games Store")

        # Create test games
        self.game1 = Game.objects.create(
            title="The Witcher 3",
            play_priority=9,
            played=False,
            controller_support=True,
            max_players=1,
        )

        self.game2 = Game.objects.create(
            title="Cyberpunk 2077",
            play_priority=8,
            played=True,
            controller_support=True,
            max_players=1,
        )

        self.game3 = Game.objects.create(
            title="Portal 2",
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

    def test_game_list_search_by_title(self):
        url = reverse("game-list-create-api")
        response = self.client.get(
            url, {"search": "witcher"}, **self._get_auth_headers()
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "The Witcher 3")

    def test_game_list_search_case_insensitive(self):
        url = reverse("game-list-create-api")
        response = self.client.get(
            url, {"search": "PORTAL"}, **self._get_auth_headers()
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "Portal 2")

    def test_game_list_search_partial_match(self):
        url = reverse("game-list-create-api")
        response = self.client.get(url, {"search": "cyber"}, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "Cyberpunk 2077")

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
            "title": "New Game",
            "platform_id": self.platform1.id,
            "vendor_id": self.vendor1.id,
            "price": "29.99",
            "added": "2023-01-01"
        }
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "New Game")

    def test_create_game_without_date_uses_current_date(self):
        url = reverse("game-list-create-api")
        data = {
            "title": "Another Game",
            "platform_id": self.platform1.id,
            "vendor_id": self.vendor1.id,
            "price": "39.99"
        }
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        game_on_platform = GameOnPlatform.objects.get(game__title="Another Game")
        self.assertEqual(game_on_platform.added, timezone.now().date())

    def test_create_game_with_invalid_platform_fails(self):
        url = reverse("game-list-create-api")
        data = {
            "title": "Invalid Game",
            "platform_id": 999,
            "vendor_id": self.vendor1.id,
            "price": "29.99"
        }
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("platform_id", response.data)

    def test_create_game_with_invalid_vendor_fails(self):
        url = reverse("game-list-create-api")
        data = {
            "title": "Invalid Game",
            "platform_id": self.platform1.id,
            "vendor_id": 999,
            "price": "29.99"
        }
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("vendor_id", response.data)

    def test_create_game_without_required_fields_fails(self):
        url = reverse("game-list-create-api")
        data = {"title": "Incomplete Game"}
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("platform_id", response.data)
        self.assertIn("vendor_id", response.data)
        self.assertIn("price", response.data)


class GameDetailAPIViewTestCase(GameAPITestCase):
    def test_game_detail_with_auth_succeeds(self):
        """Test that authenticated requests to detail endpoint work"""
        url = reverse("game-detail-api", kwargs={"id": self.game1.id})
        response = self.client.get(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.game1.id))
        self.assertEqual(response.data["title"], "The Witcher 3")

    def test_game_detail_includes_all_fields(self):
        """Test that detail response includes all expected fields"""
        url = reverse("game-detail-api", kwargs={"id": self.game1.id})
        response = self.client.get(url, **self._get_auth_headers())

        expected_fields = [
            "id",
            "title",
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
        from uuid import uuid4

        nonexistent_id = uuid4()
        url = reverse("game-detail-api", kwargs={"id": nonexistent_id})
        response = self.client.get(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class APITokenAuthenticationTestCase(GameAPITestCase):
    def test_auth_with_bearer_token(self):
        """Test authentication with Bearer token in header"""
        url = reverse("game-list-api")
        response = self.client.get(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_auth_with_url_parameter(self):
        """Test authentication with token in URL parameter"""
        url = reverse("game-list-api")
        response = self.client.get(url, {"api_token": settings.API_TOKEN})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_auth_with_invalid_token_fails(self):
        """Test that invalid token returns 403"""
        url = reverse("game-list-api")
        response = self.client.get(url, HTTP_AUTHORIZATION="Bearer invalid-token")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_auth_with_wrong_token_type_fails(self):
        """Test that wrong token type returns 403"""
        url = reverse("game-list-api")
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Token {settings.API_TOKEN}"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
