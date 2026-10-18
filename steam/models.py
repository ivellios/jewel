from typing import cast

from django.db import models

from fuzzywuzzy import process  # type: ignore[import-untyped]  # lacks py.typed


class SteamGameQuerySet(models.QuerySet):
    def all_names(self) -> list[str]:
        """
        Returns a list of all game names in the database.
        This value is cached for the lifetime of the QuerySet.
        """
        return list(self.values_list("name", flat=True))

    def fuzzy_search(
        self, name: str, all_names: list[str] | None = None, threshold: int = 95
    ) -> "SteamGame | None":
        """
        Perform a fuzzy search on the name field.

        First it tries to find exact matches (case-insensitive).
        Then it tries to find names with fuzzy matching.
        """
        exact_matches = self.filter(name__iexact=name)
        if exact_matches.exists():
            return cast("SteamGame | None", exact_matches.first())

        all_names = all_names or self.all_names()

        fuzzy_matches = process.extract(name, all_names)
        fuzzy_name = fuzzy_matches[0][0] if fuzzy_matches[0][1] >= threshold else None

        if not fuzzy_name:
            return None

        return cast("SteamGame", self.get(name=fuzzy_name))


class SteamGame(models.Model):
    appid = models.CharField(max_length=50)
    name = models.CharField(max_length=255)

    objects = SteamGameQuerySet.as_manager()

    def __str__(self):
        return self.name
