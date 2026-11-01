from django.conf import settings
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from games.api.__tests__.factories import UserFactory

from ..models import BGGMetadata, BoardGame
from .factories import BGGMetadataFactory, BoardGameFactory


class BoardGameAPITestCase(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.metadata = BGGMetadataFactory()
        self.board_game = BoardGameFactory(
            metadata=self.metadata,
            name="Catan",
            language="en",
            edition_label="3rd Edition",
        )

    def _get_auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {settings.API_TOKEN}"}


class BoardGameListAPITestCase(BoardGameAPITestCase):
    def test_list_without_auth_fails(self):
        url = reverse("boardgame-list-create-api")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_with_auth_succeeds(self):
        url = reverse("boardgame-list-create-api")
        response = self.client.get(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_with_all_fields(self):
        url = reverse("boardgame-list-create-api")
        data = {
            "name": "Ticket to Ride",
            "language": "de",
            "edition_label": "German Edition",
            "condition": "good",
            "storage": "closet",
            "purchase_date": "2023-05-15",
        }
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(BoardGame.objects.count(), 2)  # existing + new
        new_game = BoardGame.objects.get(id=response.data["id"])
        self.assertEqual(new_game.name, "Ticket to Ride")
        self.assertEqual(new_game.language, "de")
        self.assertEqual(new_game.edition_label, "German Edition")
        self.assertEqual(new_game.condition, "good")
        self.assertEqual(new_game.storage, "closet")
        self.assertEqual(str(new_game.purchase_date), "2023-05-15")
        # Read-only fields are NOT writable
        self.assertIsNone(new_game.metadata)
        self.assertFalse(new_game.imported)
        self.assertFalse(new_game.owned)

    def test_create_with_partial_fields(self):
        url = reverse("boardgame-list-create-api")
        data = {"name": "Simple Game"}
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_game = BoardGame.objects.get(id=response.data["id"])
        self.assertEqual(new_game.name, "Simple Game")
        self.assertIsNone(new_game.language)
        self.assertIsNone(new_game.metadata)

    def test_read_only_fields_in_response(self):
        """Test that read-only fields (imported, owned, removed, metadata)
        are present in list responses."""
        url = reverse("boardgame-list-create-api")
        response = self.client.get(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        game_data = response.data[0]
        self.assertIn("imported", game_data)
        self.assertIn("owned", game_data)
        self.assertIn("removed", game_data)
        self.assertIn("metadata", game_data)


class BoardGameDetailAPITestCase(BoardGameAPITestCase):
    def test_detail_without_auth_fails(self):
        url = reverse("boardgame-detail-api", kwargs={"id": self.board_game.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_detail_with_auth_succeeds(self):
        url = reverse("boardgame-detail-api", kwargs={"id": self.board_game.id})
        response = self.client.get(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.board_game.id))
        self.assertEqual(response.data["name"], "Catan")
        self.assertEqual(response.data["language"], "en")

    def test_detail_nonexistent_returns_404(self):
        from uuid import uuid4

        url = reverse("boardgame-detail-api", kwargs={"id": uuid4()})
        response = self.client.get(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_patch_local_fields(self):
        url = reverse("boardgame-detail-api", kwargs={"id": self.board_game.id})
        data = {"name": "Catan 5th Edition", "condition": "excellent"}
        response = self.client.patch(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.board_game.refresh_from_db()
        self.assertEqual(self.board_game.name, "Catan 5th Edition")
        self.assertEqual(self.board_game.condition, "excellent")
        # Read-only fields must NOT change
        self.assertEqual(
            self.board_game.metadata,
            BGGMetadata.objects.get(bgg_id=self.metadata.bgg_id),
        )
        self.assertFalse(self.board_game.imported)
        self.assertFalse(self.board_game.owned)

    def test_update_put_local_fields(self):
        url = reverse("boardgame-detail-api", kwargs={"id": self.board_game.id})
        data = {
            "name": "Azul",
            "language": "en",
            "edition_label": "Standalone",
            "condition": "mint",
            "storage": "shelf",
            "purchase_date": "2024-01-01",
            "play_priority": 5,
            "notes": "Love this game",
        }
        response = self.client.put(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.board_game.refresh_from_db()
        self.assertEqual(self.board_game.name, "Azul")
        self.assertEqual(self.board_game.edition_label, "Standalone")
        self.assertEqual(self.board_game.condition, "mint")
        self.assertEqual(self.board_game.storage, "shelf")
        self.assertEqual(str(self.board_game.purchase_date), "2024-01-01")
        self.assertEqual(self.board_game.play_priority, 5)
        self.assertEqual(self.board_game.notes, "Love this game")

    def test_cannot_update_read_only_metadata_field(self):
        """Attempting to update metadata (read-only FK) must not change it."""
        url = reverse("boardgame-detail-api", kwargs={"id": self.board_game.id})
        other_metadata = BGGMetadataFactory(bgg_id=999999)
        data = {"metadata": other_metadata.pk}
        self.client.patch(url, data, **self._get_auth_headers())
        # DRF 403/400 or no-op on read-only FK — key point: metadata must NOT change
        self.board_game.refresh_from_db()
        self.assertEqual(self.board_game.metadata.bgg_id, self.metadata.bgg_id)

    def test_cannot_update_read_only_flags(self):
        """Attempting to update imported/owned/removed must not change them."""
        url = reverse("boardgame-detail-api", kwargs={"id": self.board_game.id})
        data = {"imported": True, "owned": True, "removed": True}
        self.client.patch(url, data, **self._get_auth_headers())
        # Status may vary (400/403/no-op), but the important thing is:
        # the flags must NOT change on the model.
        self.board_game.refresh_from_db()
        self.assertFalse(self.board_game.imported)
        self.assertFalse(self.board_game.owned)
        self.assertFalse(self.board_game.removed)

    def test_read_response_includes_source_fields(self):
        """Read response includes metadata, imported, owned, removed."""
        url = reverse("boardgame-detail-api", kwargs={"id": self.board_game.id})
        response = self.client.get(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertIn("metadata", data)
        self.assertIn("imported", data)
        self.assertIn("owned", data)
        self.assertIn("removed", data)


class BoardGameIdReadOnlyAPITestCase(BoardGameAPITestCase):
    """Prove the UUID ``id`` field is not assignable via the API."""

    def test_create_ignores_client_provided_id(self):
        """When a client sends ``id`` on create, the server ignores it
        and generates a new UUID. The returned ``id`` must not match
        the one provided by the client."""
        from uuid import uuid4

        url = reverse("boardgame-list-create-api")
        client_id = str(uuid4())
        data = {
            "id": client_id,
            "name": "Board & Cards",
            "language": "en",
        }
        response = self.client.post(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # The server-generated UUID must differ from what the client sent.
        self.assertNotEqual(
            response.data["id"],
            client_id,
            "Create must ignore client-provided id and generate its own.",
        )
        game = BoardGame.objects.get(id=response.data["id"])
        self.assertEqual(str(game.id), response.data["id"])
        self.assertEqual(game.name, "Board & Cards")

    def test_update_ignores_client_provided_id(self):
        """When a client sends ``id`` on update, the server ignores it
        and updates the resource identified by the URL path. The stored
        ``id`` must remain unchanged."""
        from uuid import uuid4

        original_id = self.board_game.id
        url = reverse("boardgame-detail-api", kwargs={"id": original_id})
        data = {"id": str(uuid4()), "name": "Updated Name"}
        response = self.client.patch(url, data, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.board_game.refresh_from_db()
        # The stored UUID must be the original, unchanged.
        self.assertEqual(
            self.board_game.id,
            original_id,
            "Update must ignore client-provided id and keep the URL path id.",
        )
        self.assertEqual(self.board_game.name, "Updated Name")

    def test_read_response_includes_id(self):
        """Read responses must still include the ``id`` field."""
        url = reverse("boardgame-detail-api", kwargs={"id": self.board_game.id})
        response = self.client.get(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["id"], str(self.board_game.id))


class BoardGameDeleteAPITestCase(BoardGameAPITestCase):
    """Authenticated DELETE and unauthorized access for BoardGame detail."""

    def test_delete_authenticated_returns_204(self):
        """Authenticated DELETE removes the BoardGame and returns 204."""
        url = reverse("boardgame-detail-api", kwargs={"id": self.board_game.id})
        response = self.client.delete(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(BoardGame.objects.count(), 0)

    def test_delete_without_auth_returns_403(self):
        """Unauthenticated DELETE returns 403 Forbidden."""
        url = reverse("boardgame-detail-api", kwargs={"id": self.board_game.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # BoardGame must NOT be deleted
        self.assertEqual(BoardGame.objects.count(), 1)
