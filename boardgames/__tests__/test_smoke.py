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

    def test_no_models_or_migrations(self):
        """Verify no models or migration files are introduced."""
        config = apps.get_app_config("boardgames")
        # No migrations_module attribute means no migrations directory exists.
        self.assertFalse(hasattr(config, "migrations_module"))
        # Verify no models are defined (models_module is None when no models.py exists).
        self.assertIsNone(config.models_module)

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
