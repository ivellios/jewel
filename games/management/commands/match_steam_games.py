from collections.abc import Iterable
from pprint import pprint

from django.core.management import BaseCommand

from tqdm import tqdm

from games.models import GameOnPlatform, Platform
from steam.repositories import SteamGamesRepository


class Command(BaseCommand):
    def handle(self, *args, **options):
        """
        Creates a match between the Steam App ID and the game copies that do not have an identifier set.
        """
        steam_repository = SteamGamesRepository()
        steam_platform = Platform.objects.get(name="Steam")
        game_copies: Iterable[GameOnPlatform] = GameOnPlatform.objects.filter(
            platform=steam_platform, identifier__isnull=True
        )
        fuzzy_threshold = 95
        no_matches = []
        all_names = steam_repository.get_all_names()
        for game_copy in tqdm(game_copies):
            game = game_copy.game
            steam_game = steam_repository.find_by_name(
                game.name, all_names, threshold=fuzzy_threshold
            )
            if not steam_game:
                no_matches.append((game.name, game.id))
                tqdm.write(f'Could not find name "{game.name}" in Steam games DB')
                continue

            game_copy.identifier = steam_game.appid
            game_copy.save()

        print(f"Found {len(no_matches)} games with no matches:")
        for game in no_matches:
            pprint(f"- {game[0]} (ID: {game[1]})")
