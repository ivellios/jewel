from django.apps import AppConfig


class SteamConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "steam"

    def ready(self):
        from . import signals_processors  # noqa: F401

        pass
