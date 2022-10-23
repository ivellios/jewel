import logging

import requests
from django.core.management import BaseCommand
from tqdm import tqdm

from steam.models import SteamGame
from steam.repositories import SteamGamesRepository

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    LIBRARY_URL = "http://api.steampowered.com/ISteamApps/GetAppList/v0002/?format=json"
    # "http://api.steampowered.com/ISteamApps/GetAppList/v0002/?key=STEAMKEY&format=json"

    def load_library(self):
        repository = SteamGamesRepository()
        response = requests.get(self.LIBRARY_URL)
        logger.info("Status %s", response.status_code)
        if response.status_code == 200:
            games = response.json().get("applist", {}).get("apps", [])
            logger.info("Found %s games", len(games))
            for game in tqdm(games):
                repository.create(game["appid"], game["name"])

    def handle(self, *args, **options):
        self.load_library()
