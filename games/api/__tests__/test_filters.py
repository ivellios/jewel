from django.test import TestCase

from ...models import Game
from ..filters import GameFilterSet
from .factories import GameFactory


class GameFilterSetTestCase(TestCase):
    def setUp(self):
        # Create test games
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

    def test_games_filter_single_game(self):
        """Test filtering for a single game using the games filter"""
        queryset = (
            Game.objects.all_with_orphaned()
        )  # Use all_with_orphaned to include games without platforms
        filter_data = {"games": "witcher"}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)
        self.assertEqual(len(filtered_games), 1)
        self.assertEqual(filtered_games[0].name, "The Witcher 3")

    def test_games_filter_multiple_games(self):
        """Test filtering for multiple games using comma-separated names"""
        queryset = Game.objects.all_with_orphaned()
        filter_data = {"games": "witcher,cyberpunk"}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)
        self.assertEqual(len(filtered_games), 2)

        game_names = [game.name for game in filtered_games]
        self.assertIn("The Witcher 3", game_names)
        self.assertIn("Cyberpunk 2077", game_names)

    def test_games_filter_case_insensitive(self):
        """Test that the games filter is case insensitive"""
        queryset = Game.objects.all_with_orphaned()
        filter_data = {"games": "PORTAL"}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)
        self.assertEqual(len(filtered_games), 1)
        self.assertEqual(filtered_games[0].name, "Portal 2")

    def test_games_filter_partial_match(self):
        """Test that the games filter supports partial matching"""
        queryset = Game.objects.all_with_orphaned()
        filter_data = {"games": "cyber"}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)
        self.assertEqual(len(filtered_games), 1)
        self.assertEqual(filtered_games[0].name, "Cyberpunk 2077")

    def test_games_filter_with_whitespace(self):
        """Test that the games filter handles whitespace correctly"""
        queryset = Game.objects.all_with_orphaned()
        filter_data = {"games": "  witcher  ,  portal  "}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)
        self.assertEqual(len(filtered_games), 2)

        game_names = [game.name for game in filtered_games]
        self.assertIn("The Witcher 3", game_names)
        self.assertIn("Portal 2", game_names)

    def test_games_filter_no_matches(self):
        """Test that the games filter returns empty queryset when no games match"""
        queryset = Game.objects.all_with_orphaned()
        filter_data = {"games": "nonexistent"}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)
        self.assertEqual(len(filtered_games), 0)

    def test_games_filter_empty_value(self):
        """Test that empty games filter returns all games"""
        queryset = Game.objects.all_with_orphaned()
        filter_data = {"games": ""}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)
        self.assertEqual(len(filtered_games), 3)

    def test_search_filter_still_works(self):
        """Test that the single search filter still works"""
        queryset = Game.objects.all_with_orphaned()
        filter_data = {"search": "witcher"}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)
        self.assertEqual(len(filtered_games), 1)
        self.assertEqual(filtered_games[0].name, "The Witcher 3")

    def test_both_games_and_search_filters(self):
        """Test using both games and search filters together"""
        queryset = Game.objects.all_with_orphaned()
        # Use a filter combination that would match the same game
        filter_data = {"games": "witcher", "search": "witcher"}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)

        # Should return games matching both conditions (AND logic)
        self.assertEqual(len(filtered_games), 1)
        self.assertEqual(filtered_games[0].name, "The Witcher 3")


class GameFilterSetSpacesTestCase(TestCase):
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

    def test_games_filter_with_space_in_names(self):
        """Test filtering for games with spaces in their names"""
        queryset = Game.objects.all_with_orphaned()
        filter_data = {"games": "grand theft,red dead"}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)
        self.assertEqual(len(filtered_games), 2)

        game_names = [game.name for game in filtered_games]
        self.assertIn("Grand Theft Auto V", game_names)
        self.assertIn("Red Dead Redemption 2", game_names)

    def test_games_filter_full_name_with_spaces(self):
        """Test filtering using full game names that contain spaces"""
        queryset = Game.objects.all_with_orphaned()
        filter_data = {"games": "The Witcher 3,Grand Theft Auto"}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)
        self.assertEqual(len(filtered_games), 2)

        game_names = [game.name for game in filtered_games]
        self.assertIn("The Witcher 3", game_names)
        self.assertIn("Grand Theft Auto V", game_names)

    def test_games_filter_mixed_space_and_no_space_names(self):
        """Test filtering with a mix of games with and without spaces"""
        queryset = Game.objects.all_with_orphaned()
        filter_data = {"games": "cyberpunk,grand theft,portal"}
        filterset = GameFilterSet(data=filter_data, queryset=queryset)

        self.assertTrue(filterset.is_valid())
        filtered_games = list(filterset.qs)
        self.assertEqual(len(filtered_games), 3)

        game_names = [game.name for game in filtered_games]
        self.assertIn("Cyberpunk 2077", game_names)
        self.assertIn("Grand Theft Auto V", game_names)
        self.assertIn("Portal 2", game_names)
