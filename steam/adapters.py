from abstract.games import SteamGameInterface

from .models import SteamGame


class SteamGameAdapter(SteamGameInterface):
    def __init__(self, game: SteamGame, data: dict):
        self.data = data
        self.game = game

    @property
    def appid(self):
        return self.game.appid

    @property
    def name(self):
        return self.game.name

    @property
    def description(self):
        return self.data.get("short_description")

    @property
    def platforms(self):
        platforms = self.data.get("platforms")
        return [platform for platform in platforms if platforms.get(platform) is True]

    @property
    def metacritic(self):
        return self.data.get("metacritic", {}).get("score")

    @property
    def metacritic_url(self):
        return self.data.get("metacritic", {}).get("url")

    @property
    def categories(self):
        return [category.get("description") for category in self.data.get("categories")]

    @property
    def genres(self):
        return [genre.get("description") for genre in self.data.get("genres")]

    @property
    def recommendations(self):
        return self.data.get("recommendations")
