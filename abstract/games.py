import abc
from datetime import datetime
from decimal import Decimal


class PlatformInterface(abc.ABC):
    name: str


class GameOnPlatformInterface(abc.ABC):
    platform: PlatformInterface
    added: datetime | None
    source: str | None
    price: Decimal | None
    identifier: str | None

    def to_dict(self):
        return {
            "platform": self.platform.name,
            "added": self.added,
            "price": self.price,
            "source": self.source,
            "identifier": self.identifier,
        }


class GameInterface(abc.ABC):
    id: str | None
    name: str
    platforms: list[GameOnPlatformInterface]
    play_priority: int | None
    played: bool = False
    controller_support: bool | None
    max_players: int | None
    party_fit: bool | None
    review: int | None
    notes: str | None
    genres: list[str]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "platforms": [platform.to_dict() for platform in self.platforms]
            if self.platforms
            else [],
            "play_priority": self.play_priority,
            "played": self.played,
            "controller_support": self.controller_support,
            "max_players": self.max_players,
            "party_fit": self.party_fit,
            "review": self.review,
            "notes": self.notes,
            "genres": self.genres if self.genres else [],
        }


class SteamGameInterface(abc.ABC):
    appid: str
    name: str
    description: str | None
    platforms: list | None
    metacritic: int | None
    metacritic_url: str | None
    categories: list[str] | None
    genres: list[str] | None
    recommendations: int | None

    def to_dict(self):
        return {
            "appid": self.appid,
            "name": self.name,
            "description": self.description,
            "platforms": self.platforms,
            "metacritic": self.metacritic,
            "metacritic_url": self.metacritic_url,
            "categories": self.categories,
            "genres": self.genres,
            "recommendations": self.recommendations,
        }
