from games.models import GameOnPlatform
from steam.models import SteamGame


def set_steam_game_appid(gop: GameOnPlatform) -> bool | None:
    """
    Tries to find the best matching Steam game for a newly added GameOnPlatform instance.
    If a match is found, it sets the identifier field to the Steam app ID.

    The way it looks for the game is by doing a fuzzy search on the name of the game.
    """
    if gop.identifier:
        return None
    added_game_name = gop.game.name
    steam_games = SteamGame.objects.filter(name__iexact=added_game_name)
    if steam_games.exists():
        gop.identifier = steam_games.first().appid
        gop.save(update_fields=["identifier"])
        return True
    return False
