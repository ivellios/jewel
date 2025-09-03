import requests

from abstract.games import SteamGameInterface

from .adapters import SteamGameAdapter
from .models import SteamGame


class SteamGamesRepository:
    @staticmethod
    def create(appid, name):
        try:
            SteamGame.objects.get(name=name)
        except SteamGame.DoesNotExist:
            SteamGame.objects.create(appid=appid, name=name)

    @staticmethod
    def get_all_names() -> list[str]:
        return SteamGame.objects.all_names()

    @staticmethod
    def find_by_name(
        name, all_names: list[str] = None, threshold: int = 95
    ) -> SteamGame | None:
        return SteamGame.objects.fuzzy_search(name, all_names, threshold=threshold)

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
