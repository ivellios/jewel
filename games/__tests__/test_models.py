from django.test import TestCase
from django.utils import timezone

from games.api.__tests__.factories import GameFactory, PlatformFactory
from games.models import Game, GameOnPlatform


class GameManagerTestCase(TestCase):
    def setUp(self):
        self.platform1 = PlatformFactory(name="Steam")
        self.platform2 = PlatformFactory(name="Epic Games")

        # Game with active platforms
        self.game_with_platforms = GameFactory(name="Active Game", platforms=False)
        self.active_gop1 = GameOnPlatform.objects.create(
            game=self.game_with_platforms, platform=self.platform1
        )
        self.active_gop2 = GameOnPlatform.objects.create(
            game=self.game_with_platforms, platform=self.platform2
        )

        # Game with all platforms deleted
        self.orphaned_game = GameFactory(name="Orphaned Game", platforms=False)
        self.deleted_gop1 = GameOnPlatform.objects.create(
            game=self.orphaned_game,
            platform=self.platform1,
            deleted=True,
            deleted_at=timezone.now(),
        )
        self.deleted_gop2 = GameOnPlatform.objects.create(
            game=self.orphaned_game,
            platform=self.platform2,
            deleted=True,
            deleted_at=timezone.now(),
        )

        # Game with mixed platforms (some deleted, some active)
        self.mixed_game = GameFactory(name="Mixed Game", platforms=False)
        self.mixed_active_gop = GameOnPlatform.objects.create(
            game=self.mixed_game, platform=self.platform1
        )
        self.mixed_deleted_gop = GameOnPlatform.objects.create(
            game=self.mixed_game,
            platform=self.platform2,
            deleted=True,
            deleted_at=timezone.now(),
        )

        # Game with no platforms at all
        self.no_platforms_game = GameFactory(name="No Platforms Game", platforms=False)

    def test_default_queryset_excludes_orphaned_games(self):
        """Test that Game.objects.all() excludes games with no active platforms"""
        games = Game.objects.all()
        game_names = [game.name for game in games]

        # Should include games with active platforms
        self.assertIn("Active Game", game_names)
        self.assertIn("Mixed Game", game_names)

        # Should exclude orphaned games and games with no platforms
        self.assertNotIn("Orphaned Game", game_names)
        self.assertNotIn("No Platforms Game", game_names)

    def test_all_with_orphaned_includes_all_games(self):
        """Test that all_with_orphaned() returns all games including orphaned"""
        games = Game.objects.all_with_orphaned()
        game_names = [game.name for game in games]

        # Should include all games
        self.assertIn("Active Game", game_names)
        self.assertIn("Mixed Game", game_names)
        self.assertIn("Orphaned Game", game_names)
        self.assertIn("No Platforms Game", game_names)

        # Should have all 4 games
        self.assertEqual(games.count(), 4)

    def test_orphaned_only_returns_only_orphaned_games(self):
        """Test that orphaned_only() returns only games with no active platforms"""
        games = Game.objects.orphaned_only()
        game_names = [game.name for game in games]

        # Should only include orphaned games
        self.assertIn("Orphaned Game", game_names)
        self.assertIn("No Platforms Game", game_names)

        # Should exclude games with active platforms
        self.assertNotIn("Active Game", game_names)
        self.assertNotIn("Mixed Game", game_names)

        # Should have exactly 2 orphaned games
        self.assertEqual(games.count(), 2)


class GameQuerySetTestCase(TestCase):
    def setUp(self):
        self.platform1 = PlatformFactory(name="Steam")
        self.platform2 = PlatformFactory(name="Epic Games")

        # Game with active platforms
        self.game_with_platforms = GameFactory(name="Active Game", platforms=False)
        GameOnPlatform.objects.create(
            game=self.game_with_platforms, platform=self.platform1
        )

        # Game with all platforms deleted
        self.orphaned_game = GameFactory(name="Orphaned Game", platforms=False)
        GameOnPlatform.objects.create(
            game=self.orphaned_game,
            platform=self.platform1,
            deleted=True,
            deleted_at=timezone.now(),
        )

        # Game with no platforms
        self.no_platforms_game = GameFactory(name="No Platforms Game", platforms=False)

    def test_with_active_platforms_method(self):
        """Test GameQuerySet.with_active_platforms() method"""
        games = Game.objects.all_with_orphaned().with_active_platforms()
        game_names = [game.name for game in games]

        # Should only include games with active platforms
        self.assertIn("Active Game", game_names)

        # Should exclude orphaned and no-platform games
        self.assertNotIn("Orphaned Game", game_names)
        self.assertNotIn("No Platforms Game", game_names)

        self.assertEqual(games.count(), 1)

    def test_orphaned_method(self):
        """Test GameQuerySet.orphaned() method"""
        games = Game.objects.all_with_orphaned().orphaned()
        game_names = [game.name for game in games]

        # Should include orphaned games
        self.assertIn("Orphaned Game", game_names)
        self.assertIn("No Platforms Game", game_names)

        # Should exclude games with active platforms
        self.assertNotIn("Active Game", game_names)

        self.assertEqual(games.count(), 2)

    def test_chaining_queryset_methods(self):
        """Test that queryset methods can be chained properly"""
        # Test that we can chain from all_with_orphaned to specific filters
        active_games = Game.objects.all_with_orphaned().with_active_platforms()
        orphaned_games = Game.objects.all_with_orphaned().orphaned()

        # Counts should add up to total
        total_games = Game.objects.all_with_orphaned().count()
        self.assertEqual(active_games.count() + orphaned_games.count(), total_games)


class GameOnPlatformSoftDeleteTestCase(TestCase):
    def setUp(self):
        self.platform = PlatformFactory(name="Steam")
        self.game = GameFactory(name="Test Game", platforms=False)
        self.game_platform = GameOnPlatform.objects.create(
            game=self.game, platform=self.platform
        )

    def test_soft_delete_sets_deleted_fields(self):
        """Test that soft_delete() sets deleted=True and deleted_at"""
        self.assertFalse(self.game_platform.deleted)
        self.assertIsNone(self.game_platform.deleted_at)

        self.game_platform.soft_delete()

        self.assertTrue(self.game_platform.deleted)
        self.assertIsNotNone(self.game_platform.deleted_at)

    def test_restore_clears_deleted_fields(self):
        """Test that restore() clears deleted fields"""
        # First soft delete
        self.game_platform.soft_delete()
        self.assertTrue(self.game_platform.deleted)
        self.assertIsNotNone(self.game_platform.deleted_at)

        # Then restore
        self.game_platform.restore()

        self.assertFalse(self.game_platform.deleted)
        self.assertIsNone(self.game_platform.deleted_at)

    def test_game_visibility_changes_with_soft_delete(self):
        """Test that game visibility changes when all platforms are soft deleted"""
        # Game should be visible initially
        self.assertTrue(Game.objects.filter(id=self.game.id).exists())

        # Soft delete the platform
        self.game_platform.soft_delete()

        # Game should no longer be visible in default queryset
        self.assertFalse(Game.objects.filter(id=self.game.id).exists())

        # But should be visible in all_with_orphaned
        self.assertTrue(
            Game.objects.all_with_orphaned().filter(id=self.game.id).exists()
        )

        # And should be in orphaned_only
        self.assertTrue(Game.objects.orphaned_only().filter(id=self.game.id).exists())
