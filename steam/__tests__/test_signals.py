from unittest.mock import patch

from django.test import TestCase

from games.api.__tests__.factories import GameFactory, PlatformFactory, VendorFactory
from games.models import GameOnPlatform
from games.signals import platform_added_for_game


class SteamSignalProcessingTestCase(TestCase):
    """Test Steam signal processing functionality"""

    def setUp(self):
        self.steam_platform = PlatformFactory(name="Steam")
        self.epic_platform = PlatformFactory(name="Epic Games")
        self.vendor = VendorFactory(name="Steam")
        self.game = GameFactory(name="Test Game")

    @patch("steam.signals_processors.set_steam_game_appid")
    def test_signal_calls_set_steam_game_appid_for_steam_platform(
        self, mock_set_steam_appid
    ):
        """Test that signal calls set_steam_game_appid for Steam platforms without identifier"""
        # Create GameOnPlatform for Steam without identifier
        gop = GameOnPlatform.objects.create(
            game=self.game,
            platform=self.steam_platform,
            vendor=self.vendor,
            identifier="",  # No identifier set
        )

        # Send the signal manually to test the receiver
        platform_added_for_game.send(sender=GameOnPlatform, instance=gop)

        # Verify the function was called with the GameOnPlatform instance
        # Note: It might be called more than once due to signal firing during object creation
        mock_set_steam_appid.assert_called_with(gop)
        self.assertGreaterEqual(mock_set_steam_appid.call_count, 1)

    @patch("steam.signals_processors.set_steam_game_appid")
    def test_signal_skips_non_steam_platforms(self, mock_set_steam_appid):
        """Test that signal skips non-Steam platforms"""
        # Create GameOnPlatform for Epic Games
        gop = GameOnPlatform.objects.create(
            game=self.game,
            platform=self.epic_platform,
            vendor=self.vendor,
            identifier="",
        )

        # Send the signal
        platform_added_for_game.send(sender=GameOnPlatform, instance=gop)

        # Verify the function was NOT called
        mock_set_steam_appid.assert_not_called()

    @patch("steam.signals_processors.set_steam_game_appid")
    def test_signal_skips_steam_games_with_existing_identifier(
        self, mock_set_steam_appid
    ):
        """Test that signal skips Steam games that already have identifiers"""
        # Create GameOnPlatform for Steam WITH identifier
        gop = GameOnPlatform.objects.create(
            game=self.game,
            platform=self.steam_platform,
            vendor=self.vendor,
            identifier="123456",  # Already has identifier
        )

        # Send the signal
        platform_added_for_game.send(sender=GameOnPlatform, instance=gop)

        # Verify the function was NOT called
        mock_set_steam_appid.assert_not_called()

    @patch("steam.signals_processors.set_steam_game_appid")
    def test_signal_processes_case_insensitive_steam_platform(
        self, mock_set_steam_appid
    ):
        """Test that signal works with different case variations of Steam platform name"""
        # Create platforms with different case variations
        steam_lower = PlatformFactory(name="steam")
        steam_upper = PlatformFactory(name="STEAM")

        # Test lowercase
        gop1 = GameOnPlatform.objects.create(
            game=self.game, platform=steam_lower, vendor=self.vendor, identifier=""
        )
        platform_added_for_game.send(sender=GameOnPlatform, instance=gop1)
        mock_set_steam_appid.assert_called_with(gop1)

        mock_set_steam_appid.reset_mock()

        # Test uppercase
        gop2 = GameOnPlatform.objects.create(
            game=GameFactory(name="Test Game 2"),
            platform=steam_upper,
            vendor=self.vendor,
            identifier="",
        )
        platform_added_for_game.send(sender=GameOnPlatform, instance=gop2)
        mock_set_steam_appid.assert_called_with(gop2)

    @patch("steam.signals_processors.set_steam_game_appid")
    def test_signal_automatically_fires_on_steam_gameonplatform_creation(
        self, mock_set_steam_appid
    ):
        """Test that signal automatically fires when creating a Steam GameOnPlatform"""
        # Clear any previous calls from setup
        mock_set_steam_appid.reset_mock()

        # Create a GameOnPlatform with Steam platform and no identifier
        # This should automatically trigger our signal receiver
        gop = GameOnPlatform.objects.create(
            game=GameFactory(name="Auto Signal Test Game"),
            platform=self.steam_platform,
            vendor=self.vendor,
            identifier="",
        )

        # Verify the signal receiver was called automatically
        mock_set_steam_appid.assert_called_with(gop)
