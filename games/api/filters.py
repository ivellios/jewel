from django.db.models import Q

import django_filters

from ..models import Game


class EnhancedSearchFilter(django_filters.CharFilter):
    """
    Enhanced search filter that allows searching for multiple games by name.
    Accepts comma-separated game names and performs case-insensitive partial matching.
    Also works for single game searches.
    """

    def filter(self, qs, value):
        if not value:
            return qs

        # Check if the search contains commas (multiple games)
        if "," in value:
            # Split the value by commas and strip whitespace
            game_names = [name.strip() for name in value.split(",") if name.strip()]

            if not game_names:
                return qs

            # Build Q objects for each game name using case-insensitive partial matching
            q_objects = Q()
            for name in game_names:
                q_objects |= Q(name__icontains=name)

            return qs.filter(q_objects)
        else:
            # Single game search - use the standard icontains lookup
            return qs.filter(name__icontains=value)


class GameFilterSet(django_filters.FilterSet):
    """
    FilterSet for Game model with enhanced search functionality.
    """

    search = EnhancedSearchFilter(
        field_name="name",
        help_text="Search for games by name. Supports multiple comma-separated names (e.g., 'witcher,cyberpunk,portal')",
    )

    class Meta:
        model = Game
        fields = ["search"]
