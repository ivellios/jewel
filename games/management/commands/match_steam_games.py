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
        matches = []
        multiple_matches = []
        for game_copy in tqdm(game_copies):
            game = game_copy.game
            steam_game, score = steam_repository.find_by_name(game.title)
            if steam_game is None:
                multiple_matches.append((game.title, game.id))
                tqdm.write(f'Multiple exact matches found for "{game.title}"')
                continue

            if score == 100:
                game_copy.identifier = steam_game.appid
                game_copy.save()
            if score < 100:
                matches.append(
                    (game.title, game.id, steam_game.name, steam_game.appid, score)
                )
                tqdm.write(f"{steam_game}, {game.title}, {score}")
            # details = steam_repository.pull_game(steam_game)

        print(f"Found {len(matches)} matches that need manual review")
        for game in matches:
            pprint(
                f"Match: {game[0]}({game[1]}) - {game[2]} (https://store.steampowered.com/api/appdetails?appids={game[3]}) | score: {game[3]}"
            )
            input("Should match be saved? (y/n)")
            if input().lower() == "y":
                GameOnPlatform.objects.filter(
                    game_id=game[1], platform=steam_platform, identifier__isnull=True
                ).update(identifier=game[3])

        print(f"Found {len(multiple_matches)} games with multiple matches")
        for game in multiple_matches:
            pprint(f"Multiple matches found for {game[0]} (ID: {game[1]})")
