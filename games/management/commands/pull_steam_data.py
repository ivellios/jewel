from django.core.management import BaseCommand
from tqdm import tqdm

from games.models import Platform, GameOnPlatform
from steam.repositories import SteamGamesRepository


class Command(BaseCommand):
    def handle(self, *args, **options):
        steam_repository = SteamGamesRepository()
        steam_platform = Platform.objects.get(name="Steam")
        game_copies = GameOnPlatform.objects.filter(platform=steam_platform)
        for game_copy in tqdm(game_copies):
            game = game_copy.game
            steam_game_name, score = steam_repository.find_by_name(game.title)
            if score < 100:
                tqdm.write(f"{steam_game_name}, {game.title}, {score}")
            # details = steam_repository.pull_game(steam_game)
