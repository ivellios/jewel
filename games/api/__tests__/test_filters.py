from django.test import TestCase

from ...models import Game
from ..filters import GameFilterSet
from .factories import GameFactory


class GameFilterSetTestCase(TestCase):
    def setUp(self):
        # Create test games including games with spaces in names
        self.game1 = GameFactory(
            name="The Witcher 3",
            platforms=False,  # Don't create default platform to avoid manager filtering
        )
        self.game2 = GameFactory(
            name="Cyberpunk 2077",
            platforms=False,  # Don't create default platform to avoid manager filtering
        )
        self.game3 = GameFactory(
            name="Portal 2",
            platforms=False,  # Don't create default platform to avoid manager filtering
        )
        self.game4 = GameFactory(
            name="Grand Theft Auto V",
            platforms=False,  # Don't create default platform to avoid manager filtering
        )
        self.game5 = GameFactory(
            name="Red Dead Redemption 2",
            platforms=False,  # Don't create default platform to avoid manager filtering
        )

    def test_search_single_game(self):
        """Test filtering for a single game using the search filter"""
        queryset = Game.objects.all_with_orphaned()
        filter_data = {"search": "witcher"}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)
        self.assertEqual(len(filtered_games), 1)
        self.assertEqual(filtered_games[0].name, "The Witcher 3")

    def test_search_multiple_games(self):
        """Test filtering for multiple games using comma-separated names"""
        queryset = Game.objects.all_with_orphaned()
        filter_data = {"search": "witcher,cyberpunk"}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)
        self.assertEqual(len(filtered_games), 2)

        game_names = [game.name for game in filtered_games]
        self.assertIn("The Witcher 3", game_names)
        self.assertIn("Cyberpunk 2077", game_names)

    def test_search_case_insensitive(self):
        """Test that the search filter is case insensitive"""
        queryset = Game.objects.all_with_orphaned()
        filter_data = {"search": "PORTAL"}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)
        self.assertEqual(len(filtered_games), 1)
        self.assertEqual(filtered_games[0].name, "Portal 2")

    def test_search_partial_match(self):
        """Test that the search filter supports partial matching"""
        queryset = Game.objects.all_with_orphaned()
        filter_data = {"search": "cyber"}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)
        self.assertEqual(len(filtered_games), 1)
        self.assertEqual(filtered_games[0].name, "Cyberpunk 2077")

    def test_search_with_whitespace(self):
        """Test that the search filter handles whitespace correctly"""
        queryset = Game.objects.all_with_orphaned()
        filter_data = {"search": "  witcher  ,  portal  "}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)
        self.assertEqual(len(filtered_games), 2)

        game_names = [game.name for game in filtered_games]
        self.assertIn("The Witcher 3", game_names)
        self.assertIn("Portal 2", game_names)

    def test_search_no_matches(self):
        """Test that the search filter returns empty queryset when no games match"""
        queryset = Game.objects.all_with_orphaned()
        filter_data = {"search": "nonexistent"}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)
        self.assertEqual(len(filtered_games), 0)

    def test_search_empty_value(self):
        """Test that empty search filter returns all games"""
        queryset = Game.objects.all_with_orphaned()
        filter_data = {"search": ""}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)
        self.assertEqual(len(filtered_games), 5)

    def test_search_with_space_in_names(self):
        """Test filtering for games with spaces in their names"""
        queryset = Game.objects.all_with_orphaned()
        filter_data = {"search": "grand theft,red dead"}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)
        self.assertEqual(len(filtered_games), 2)

        game_names = [game.name for game in filtered_games]
        self.assertIn("Grand Theft Auto V", game_names)
        self.assertIn("Red Dead Redemption 2", game_names)

    def test_search_full_name_with_spaces(self):
        """Test filtering using full game names that contain spaces"""
        queryset = Game.objects.all_with_orphaned()
        filter_data = {"search": "The Witcher 3,Grand Theft Auto"}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)
        self.assertEqual(len(filtered_games), 2)

        game_names = [game.name for game in filtered_games]
        self.assertIn("The Witcher 3", game_names)
        self.assertIn("Grand Theft Auto V", game_names)

    def test_search_mixed_space_and_no_space_names(self):
        """Test filtering with a mix of games with and without spaces"""
        queryset = Game.objects.all_with_orphaned()
        filter_data = {"search": "cyberpunk,grand theft,portal"}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)
        self.assertEqual(len(filtered_games), 3)

        game_names = [game.name for game in filtered_games]
        self.assertIn("Cyberpunk 2077", game_names)
        self.assertIn("Grand Theft Auto V", game_names)
        self.assertIn("Portal 2", game_names)
