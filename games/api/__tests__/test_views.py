from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from django.conf import settings
from ...models import Game, Platform, Genre


class GameAPITestCase(APITestCase):
    def setUp(self):
        # Create a staff user for authentication
        self.staff_user = User.objects.create_user(
            username='teststaff',
            email='test@example.com',
            password='testpass',
            is_staff=True,
            is_active=True
        )
        
        # Create test games
        self.game1 = Game.objects.create(
            title='The Witcher 3',
            play_priority=9,
            played=False,
            controller_support=True,
            max_players=1
        )
        
        self.game2 = Game.objects.create(
            title='Cyberpunk 2077',
            play_priority=8,
            played=True,
            controller_support=True,
            max_players=1
        )
        
        self.game3 = Game.objects.create(
            title='Portal 2',
            play_priority=10,
            played=True,
            controller_support=False,
            max_players=2
        )
    
    def _get_auth_headers(self):
        """Helper to get authentication headers"""
        return {'HTTP_AUTHORIZATION': f'Bearer {settings.API_TOKEN}'}
    
    def test_game_list_without_auth_fails(self):
        """Test that list endpoint requires authentication"""
        url = reverse('game-list-api')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_game_detail_without_auth_fails(self):
        """Test that detail endpoint requires authentication"""
        url = reverse('game-detail-api', kwargs={'id': self.game1.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class GameListAPIViewTestCase(GameAPITestCase):
    def test_game_list_with_auth_succeeds(self):
        """Test that authenticated requests to list endpoint work"""
        url = reverse('game-list-api')
        response = self.client.get(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
    
    def test_game_list_search_by_title(self):
        """Test searching games by title"""
        url = reverse('game-list-api')
        response = self.client.get(
            url, 
            {'search': 'witcher'}, 
            **self._get_auth_headers()
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'The Witcher 3')
    
    def test_game_list_search_case_insensitive(self):
        """Test that search is case insensitive"""
        url = reverse('game-list-api')
        response = self.client.get(
            url, 
            {'search': 'PORTAL'}, 
            **self._get_auth_headers()
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Portal 2')
    
    def test_game_list_search_partial_match(self):
        """Test that search works with partial matches"""
        url = reverse('game-list-api')
        response = self.client.get(
            url, 
            {'search': 'cyber'}, 
            **self._get_auth_headers()
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Cyberpunk 2077')
    
    def test_game_list_search_no_results(self):
        """Test search with no matching results"""
        url = reverse('game-list-api')
        response = self.client.get(
            url, 
            {'search': 'nonexistent'}, 
            **self._get_auth_headers()
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


class GameDetailAPIViewTestCase(GameAPITestCase):
    def test_game_detail_with_auth_succeeds(self):
        """Test that authenticated requests to detail endpoint work"""
        url = reverse('game-detail-api', kwargs={'id': self.game1.id})
        response = self.client.get(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.game1.id))
        self.assertEqual(response.data['title'], 'The Witcher 3')
    
    def test_game_detail_includes_all_fields(self):
        """Test that detail response includes all expected fields"""
        url = reverse('game-detail-api', kwargs={'id': self.game1.id})
        response = self.client.get(url, **self._get_auth_headers())
        
        expected_fields = [
            'id', 'title', 'play_priority', 'played', 'controller_support',
            'max_players', 'party_fit', 'review', 'notes', 'genres',
            'platforms_meta_data'
        ]
        
        for field in expected_fields:
            self.assertIn(field, response.data)
    
    def test_game_detail_nonexistent_returns_404(self):
        """Test that requesting nonexistent game returns 404"""
        from uuid import uuid4
        nonexistent_id = uuid4()
        url = reverse('game-detail-api', kwargs={'id': nonexistent_id})
        response = self.client.get(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class APITokenAuthenticationTestCase(GameAPITestCase):
    def test_auth_with_bearer_token(self):
        """Test authentication with Bearer token in header"""
        url = reverse('game-list-api')
        response = self.client.get(url, **self._get_auth_headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_auth_with_url_parameter(self):
        """Test authentication with token in URL parameter"""
        url = reverse('game-list-api')
        response = self.client.get(url, {'api_token': settings.API_TOKEN})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_auth_with_invalid_token_fails(self):
        """Test that invalid token returns 403"""
        url = reverse('game-list-api')
        response = self.client.get(
            url, 
            HTTP_AUTHORIZATION='Bearer invalid-token'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_auth_with_wrong_token_type_fails(self):
        """Test that wrong token type returns 403"""
        url = reverse('game-list-api')
        response = self.client.get(
            url, 
            HTTP_AUTHORIZATION=f'Token {settings.API_TOKEN}'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)