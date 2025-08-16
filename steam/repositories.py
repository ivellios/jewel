import requests

from abstract.games import SteamGameInterface
from .adapters import SteamGameAdapter
from .models import SteamGame
from fuzzywuzzy import fuzz
from fuzzywuzzy import process


class SteamGamesRepository:
    @staticmethod
    def create(appid, name):
        return SteamGame.objects.update_or_create(appid=appid, name=name)

    @staticmethod
    def find_by_name(name) -> tuple[SteamGame | None, int]:
        max_ratio = 0
        max_ratio_game = None
        try:
            game = SteamGame.objects.get(name=name)
            max_ratio = 100
        except SteamGame.MultipleObjectsReturned:
            print(f"Multiple games: {name}")
            return None, 0
        except SteamGame.DoesNotExist:
            for game in SteamGame.objects.all().iterator():
                ratio = fuzz.token_sort_ratio(name, game.name)
                if ratio > max_ratio:
                    max_ratio = ratio
                    max_ratio_game = game.appid
            try:
                game = SteamGame.objects.get(appid=max_ratio_game)
            except SteamGame.MultipleObjectsReturned as e:
                return None, 0

        return game, max_ratio

    @staticmethod
    def pull_game(game: SteamGame) -> SteamGameInterface | None:
        response = requests.get(
            f"https://store.steampowered.com/api/appdetails?appids={game.appid}"
        )
        if response.status_code == 200:
            return SteamGameAdapter(game, response.json())

    @staticmethod
    def find_one(appid: str) -> SteamGame | None:
        try:
            return SteamGame.objects.get(appid=appid)
        except SteamGame.DoesNotExist:
            return
