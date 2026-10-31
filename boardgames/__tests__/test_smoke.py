"""Smoke test verifying the boardgames app loads cleanly in Django."""

from django.apps import apps
from django.test import TestCase


class BoardgamesAppSmokeTest(TestCase):
    """Verify boardgames app scaffolding is correctly registered."""

    def test_boardgames_in_installed_apps(self):
        """Verify boardgames is registered in INSTALLED_APPS."""
        self.assertIn("boardgames", apps.app_configs)

    def test_boardgames_config_exists(self):
        """Verify BoardgamesConfig is loadable without side effects."""
        config = apps.get_app_config("boardgames")
        self.assertIsNotNone(config)
        self.assertEqual(config.name, "boardgames")
        self.assertEqual(config.default_auto_field, "django.db.models.BigAutoField")

    def test_models_and_migrations_exist(self):
        """Verify boardgames now defines models and has a migrations module."""
        import os

        from boardgames.models import (
            BGGExpansion,
            BGGMetadata,
            BGGSyncRun,
        )

        # Migrations directory should now exist.
        migrations_dir = os.path.join(
            os.path.dirname(__file__), "..", "migrations"
        )
        self.assertTrue(os.path.isdir(migrations_dir))

        # Verify models are importable.
        self.assertIsNotNone(BGGMetadata)
        self.assertIsNotNone(BGGSyncRun)
        self.assertIsNotNone(BGGExpansion)

    def test_games_unchanged(self):
        """Verify existing games app is unaffected."""
        config = apps.get_app_config("games")
        self.assertIsNotNone(config)
        self.assertEqual(config.name, "games")

    def test_steam_unchanged(self):
        """Verify existing steam app is unaffected."""
        config = apps.get_app_config("steam")
        self.assertIsNotNone(config)
        self.assertEqual(config.name, "steam")
