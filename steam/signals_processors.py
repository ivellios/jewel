from django.dispatch import receiver

from games.models import GameOnPlatform
from games.signals import platform_added_for_game
from steam.utils import set_steam_game_appid


@receiver(platform_added_for_game, sender=GameOnPlatform)
def add_steam_game_id_for_new_game(sender, instance: GameOnPlatform, **kwargs):
    if instance.platform.name.lower() != "steam" or instance.identifier:
        return
    set_steam_game_appid(instance)
