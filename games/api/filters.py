from django.db.models import Q

import django_filters

from ..models import Game


class MultipleGameNameFilter(django_filters.CharFilter):
    """
    Custom filter that allows searching for multiple games by name.
    Accepts comma-separated game names and performs case-insensitive partial matching.
    """

    def filter(self, qs, value):
        if not value:
            return qs

        # Split the value by commas and strip whitespace
        game_names = [name.strip() for name in value.split(",") if name.strip()]

        if not game_names:
            return qs

        # Build Q objects for each game name using case-insensitive partial matching
        q_objects = Q()
        for name in game_names:
            q_objects |= Q(name__icontains=name)

        return qs.filter(q_objects)


class GameFilterSet(django_filters.FilterSet):
    """
    FilterSet for Game model with custom multiple game name search.
    """

    games = MultipleGameNameFilter(
        help_text="Search for multiple games using comma-separated names (e.g., 'witcher,cyberpunk,portal')"
    )
    # Keep the existing single search functionality as well
    search = django_filters.CharFilter(
        field_name="name",
        lookup_expr="icontains",
        help_text="Search for a single game by name",
    )

    class Meta:
        model = Game
        fields = ["games", "search"]
