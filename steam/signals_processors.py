from django.dispatch import receiver

from games.models import GameOnPlatform
from games.signals import platform_added_for_game
from steam.models import SteamGame


@receiver(platform_added_for_game, sender=GameOnPlatform)
def add_steam_game_id_for_new_game(sender, instance: GameOnPlatform, **kwargs):
    """
    Tries to find the best matching Steam game for a newly added GameOnPlatform instance.
    If a match is found, it sets the identifier field to the Steam app ID.

    The way it looks for the game is by doing a fuzzy search on the name of the game.
    """
    if instance.platform.name.lower() != "steam" or instance.identifier:
        return
    added_game_name = instance.game.name
    steam_games = SteamGame.objects.filter(name__iexact=added_game_name)
    if steam_games.exists():
        instance.identifier = steam_games.first().appid
        instance.save(update_fields=["identifier"])
