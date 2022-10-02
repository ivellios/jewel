from datetime import datetime

from price_parser import Price

from abstract.games import GameInterface, PlatformInterface, GameOnPlatformInterface


class CSVPlatformAdapter(PlatformInterface):
    def __init__(self, name: str):
        self.name = name


class CSVGameOnPlatformAdapter(GameOnPlatformInterface):
    def __init__(self, data: dict):
        self.data = data
        self.identifier = None

    @property
    def name(self) -> str:
        return self.data.get("name")

    @property
    def price(self):
        price = Price.fromstring(self.data.get("price"))
        return price.amount

    @property
    def added(self):
        try:
            return datetime.strptime(self.data.get("added"), "%Y-%m-%d")
        except (ValueError, TypeError):
            return None

    @property
    def source(self):
        return self.data.get("source")

    @property
    def platform(self):
        return CSVPlatformAdapter(self.name.strip())


class CSVGameAdapter(GameInterface):
    def __init__(self, data: dict):
        self.data = data

    def _convert_to_int(self, key):
        value = self.data.get(key)
        try:
            return int(value[:2]) if value else None
        except (ValueError, TypeError):
            try:
                return int(value[-1])
            except (ValueError, TypeError):
                try:
                    return int(value[0])
                except (ValueError, TypeError):
                    return None

    @property
    def id(self):
        return None

    @property
    def title(self):
        return self.data.get("title")

    @property
    def platforms(self):
        p1, p2, p3 = (
            self.data.get("platform_1"),
            self.data.get("platform_2"),
            self.data.get("platform_3"),
        )

        # almost always added, price and source come for the first added platform
        data_p1 = {
            "name": p1,
            "price": self.data.get("price"),
            "added": self.data.get("added"),
            "source": self.data.get("source"),
        }

        gops = [
            CSVGameOnPlatformAdapter(data_p1) if p1 else None,
            CSVGameOnPlatformAdapter({"name": p2}) if p2 else None,
            CSVGameOnPlatformAdapter({"name": p3}) if p3 else None,
        ]
        return [gop for gop in gops if gop]

    @property
    def play_priority(self):
        return self._convert_to_int("play_priority")

    @property
    def played(self):
        value = self.data.get("played")
        return bool(int(value)) if value is not None else None

    @property
    def controller_support(self):
        value = self.data.get("controller_support")
        try:
            return bool(int(value)) if value is not None else None
        except (ValueError, TypeError):
            return None

    @property
    def max_players(self):
        return self._convert_to_int("max_players")

    @property
    def party_fit(self):
        value = self.data.get("party_fit")
        return bool(value)

    @property
    def review(self):
        return self._convert_to_int("review")

    @property
    def notes(self):
        return self.data.get("notes")

    @property
    def genres(self):
        genre = self.data.get("genre")
        return [genre] if genre else []
