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
    title: str
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
            "title": self.title,
            "platforms": [platform.to_dict() for platform in self.platforms]
            if self.platforms
            else list(),
            "play_priority": self.play_priority,
            "played": self.played,
            "controller_support": self.controller_support,
            "max_players": self.max_players,
            "party_fit": self.party_fit,
            "review": self.review,
            "notes": self.notes,
            "genres": self.genres if self.genres else list(),
        }
