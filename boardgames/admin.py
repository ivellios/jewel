"""Safe Django admin surfaces for the boardgames app.

BoardGame: editable local fields (name, language, edition_label, condition,
storage, purchase_date, inherited CollectionItem fields); read-only
source/ownership fields (metadata, imported, owned, removed).

BGGMetadata: read-only source metadata — BGG-owned fields only.

BGGExpansion: read-only relationship data — derived from BGG.

BGGSyncRun: read-only diagnostic records — run lifecycle, counters, errors.
"""

import re
from collections.abc import Mapping

from django.contrib import admin
from django.db.models import Prefetch, Q
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from boardgames.models import (
    BGGExpansion,
    BGGMetadata,
    BGGSyncRun,
    BoardGame,
)


def _metadata_destination(metadata: BGGMetadata):
    """Link to an active local copy, or fall back to the canonical BGG page."""
    copies = getattr(metadata, "admin_active_copies", None)
    if copies is None:
        copies = list(
            metadata.copies.filter(removed=False).order_by("imported", "id")[:1]
        )
    if copies:
        copy = copies[0]
        return format_html(
            '<a href="{url}">{label}</a>',
            url=reverse("admin:boardgames_boardgame_change", args=[copy.pk]),
            label=copy.display_name,
        )
    title = metadata.name or f"BGG #{metadata.bgg_id}"
    return format_html(
        '<a href="{url}" target="_blank" rel="noopener">{label}</a>',
        url=_bgg_url(metadata),
        label=title,
    )


def _display_value(value: object | None) -> str:
    return "—" if value is None else str(value)


def _range_label(minimum: int | None, maximum: int | None) -> str:
    if minimum is None and maximum is None:
        return "—"
    if minimum is None:
        return f"Up to {maximum}"
    if maximum is None:
        return f"{minimum}+"
    if minimum == maximum:
        return str(minimum)
    return f"{minimum}–{maximum}"


# ------------------------------------------------------------------ #
# BoardGameAdmin
# ------------------------------------------------------------------ #


class HasBGGRankFilter(admin.SimpleListFilter):
    title = "Has BGG Rank"
    parameter_name = "has_bgg_rank"

    def lookups(self, request, model_admin):
        return (("yes", "Yes"), ("no", "No"))

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(metadata__boardgame_rank__isnull=False)
        if self.value() == "no":
            return queryset.filter(metadata__boardgame_rank__isnull=True)
        return queryset


class PlayingTimeFilter(admin.SimpleListFilter):
    title = "BGG playing time"
    parameter_name = "bgg_playing_time"

    def lookups(self, request, model_admin):
        return (
            ("up_to_30", "Up to 30 min"),
            ("31_to_60", "31–60 min"),
            ("61_to_120", "61–120 min"),
            ("over_120", "Over 120 min"),
            ("unknown", "Unknown"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == "up_to_30":
            return queryset.filter(metadata__playingtime__lte=30)
        if value == "31_to_60":
            return queryset.filter(metadata__playingtime__range=(31, 60))
        if value == "61_to_120":
            return queryset.filter(metadata__playingtime__range=(61, 120))
        if value == "over_120":
            return queryset.filter(metadata__playingtime__gt=120)
        if value == "unknown":
            return queryset.filter(metadata__playingtime__isnull=True)
        return queryset


class OfficialPlayerCountFilter(admin.SimpleListFilter):
    """Filter games by BGG's official supported player range."""

    title = "Official player count"
    parameter_name = "official_players"

    def lookups(self, request, model_admin):
        return (
            ("1", "1 player"),
            ("2", "2 players"),
            ("3", "3 players"),
            ("4", "4 players"),
            ("5_plus", "5+ players"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value in {"1", "2", "3", "4"}:
            player_count = int(value)
            return queryset.filter(
                metadata__minplayers__lte=player_count,
                metadata__maxplayers__gte=player_count,
            )
        if value == "5_plus":
            return queryset.filter(metadata__maxplayers__gte=5)
        return queryset


class ShowRemovedFilter(admin.SimpleListFilter):
    title = "Wyświetlaj usunięte"
    parameter_name = "show_removed"

    def lookups(self, request, model_admin):
        return (("no", "Nie"), ("yes", "Tak"))

    def choices(self, changelist):
        for lookup, title in self.lookup_choices:
            yield {
                "selected": self.value() == lookup
                or (self.value() is None and lookup == "no"),
                "query_string": changelist.get_query_string(
                    {self.parameter_name: lookup}, []
                ),
                "display": title,
            }

    def queryset(self, request, queryset):
        return queryset.filter(removed=self.value() == "yes")


class ShowExpansionsFilter(admin.SimpleListFilter):
    title = "Wyświetlaj dodatki"
    parameter_name = "show_expansions"

    def lookups(self, request, model_admin):
        return (("no", "Nie"), ("yes", "Tak"))

    def choices(self, changelist):
        for lookup, title in self.lookup_choices:
            yield {
                "selected": self.value() == lookup
                or (self.value() is None and lookup == "no"),
                "query_string": changelist.get_query_string(
                    {self.parameter_name: lookup}, []
                ),
                "display": title,
            }

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset
        return queryset.filter(
            Q(metadata__isnull=True)
            | (
                Q(metadata__expansions_of__isnull=True)
                & (
                    Q(metadata__item_type__isnull=True)
                    | ~Q(
                        metadata__item_type__in=(
                            "boardgameexpansion",
                            "boardgameaccessory",
                        )
                    )
                )
            )
        )


class BoardGameAdmin(admin.ModelAdmin):
    """Board game copy admin: editable local fields, read-only source/ownership.

    - **Local physical-copy fields** (editable): name, language,
      edition_label, condition, storage, purchase_date, and all inherited
      CollectionItem fields (played, review, notes, play_priority).
    - **Canonical BGG / source fields** (read-only, visible): metadata
      (BGG source identity), imported, owned, removed.
    - **Inherited fields** (editable): all CollectionItem base-class
      fields are shown and editable for local copies.
    - **Deletion guard**: imported copies cannot be hard-deleted
      from admin.  Use the ``removed`` flag to mark reversible removal.
    """

    list_display = [
        "display_name",
        "metadata_link",
        "bgg_plays",
        "bgg_rating",
        "bgg_playing_time",
        "bgg_rank",
        "official_player_range",
        "community_player_labels",
        "best_player_labels",
        "imported",
        "language",
    ]
    list_filter = [
        "imported",
        "owned",
        ShowRemovedFilter,
        HasBGGRankFilter,
        PlayingTimeFilter,
        OfficialPlayerCountFilter,
        ShowExpansionsFilter,
        "language",
    ]
    search_fields = [
        "name",
        "metadata__name",
    ]

    # Explicitly group fields in the change form.
    fieldsets = (
        (
            "Local physical-copy data (editable)",
            {
                "fields": (
                    "name",
                    "language",
                    "edition_label",
                    "condition",
                    "storage",
                    "purchase_date",
                    "played",
                    "review",
                    "notes",
                    "play_priority",
                    "min_players",
                    "max_players",
                ),
            },
        ),
        (
            "BGG source identity & ownership state (read-only)",
            {
                "fields": (
                    "metadata_link",
                    "bgg_plays",
                    "bgg_rating",
                    "bgg_playing_time",
                    "bgg_rank",
                    "imported",
                    "owned",
                    "removed",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Expansions",
            {"fields": ("expansion_links",)},
        ),
    )

    # Source/ownership/state fields: read-only, visible for reference.
    readonly_fields = [
        "metadata",
        "imported",
        "owned",
        "removed",
        "metadata_link",
        "bgg_plays",
        "bgg_rating",
        "bgg_playing_time",
        "bgg_rank",
        "official_player_range",
        "community_player_labels",
        "best_player_labels",
        "expansion_links",
    ]

    # Deletion guard: prevent hard-deletion of imported rows.
    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.imported:
            return False
        return super().has_delete_permission(request, obj)

    # -- display helpers --

    @admin.display(description="Name")
    def display_name(self, obj: BoardGame) -> str:
        return obj.display_name

    @admin.display(description="BGG Link")
    def metadata_link(self, obj: BoardGame):
        if obj.metadata_id:
            assert obj.metadata is not None
            url = _bgg_url(obj.metadata)
            return format_html(
                '<a href="{url}" target="_blank" rel="noopener">BGG Link</a>',
                url=url,
            )
        return "— (local-only)"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "metadata",
                "metadata__collection_observation",
            )
        )

    @admin.display(
        description="BGG plays", ordering="metadata__collection_observation__numplays"
    )
    def bgg_plays(self, obj: BoardGame) -> int | str:
        observation = (
            getattr(obj.metadata, "collection_observation", None)
            if obj.metadata_id
            else None
        )
        if observation is None or observation.numplays is None:
            return "—"
        return int(observation.numplays)

    @admin.display(description="BGG rating", ordering="metadata__rating_average")
    def bgg_rating(self, obj: BoardGame) -> float | str:
        metadata = obj.metadata
        if metadata is not None and metadata.rating_average is not None:
            return metadata.rating_average
        return "—"

    @admin.display(description="BGG playing time", ordering="metadata__playingtime")
    def bgg_playing_time(self, obj: BoardGame) -> str:
        metadata = obj.metadata
        if metadata is None or metadata.playingtime is None:
            return "—"
        return f"{metadata.playingtime} min"

    @admin.display(description="BGG rank", ordering="metadata__boardgame_rank")
    def bgg_rank(self, obj: BoardGame) -> int | str:
        metadata = obj.metadata
        if metadata is not None and metadata.boardgame_rank is not None:
            return metadata.boardgame_rank
        return "—"

    @admin.display(description="Expansions")
    def expansion_links(self, obj: BoardGame):
        if obj.metadata_id is None:
            return "—"
        active_copies = BoardGame.objects.filter(removed=False).order_by(
            "imported", "id"
        )
        relations = (
            BGGExpansion.objects.filter(parent_id=obj.metadata_id)
            .select_related("expansion", "expansion__collection_observation")
            .prefetch_related(
                Prefetch(
                    "expansion__copies",
                    queryset=active_copies,
                    to_attr="admin_active_copies",
                )
            )
        )
        expansions = list(relations)
        if not expansions:
            return "—"
        rows = []
        for relation in expansions:
            metadata = relation.expansion
            copies = getattr(metadata, "admin_active_copies", [])
            observation = getattr(metadata, "collection_observation", None)
            players = _range_label(metadata.minplayers, metadata.maxplayers)
            play_time = (
                f"{metadata.playingtime} min"
                if metadata.playingtime is not None
                else "—"
            )
            in_collection = (
                "Yes"
                if copies or (observation is not None and observation.owned is True)
                else "No"
                if observation is not None and observation.owned is False
                else "—"
            )
            rows.append(
                (
                    _metadata_destination(metadata),
                    _display_value(metadata.rating_average),
                    _display_value(metadata.boardgame_rank),
                    _display_value(
                        observation.numplays if observation is not None else None
                    ),
                    players,
                    play_time,
                    in_collection,
                )
            )
        return format_html(
            '<table style="border-collapse: collapse; width: 100%;">'
            "<thead><tr>"
            "<th>Expansion</th><th>BGG rating</th><th>Rank</th>"
            "<th>Your plays</th><th>Players</th><th>Playing time</th>"
            "<th>In collection</th>"
            "</tr></thead><tbody>{}</tbody></table>",
            format_html_join(
                "",
                "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td>"
                "<td>{}</td><td>{}</td><td>{}</td></tr>",
                rows,
            ),
        )

    # -- player-count columns (Packet 3) --

    @admin.display(description="Official")
    def official_player_range(self, obj: BoardGame) -> str:
        """BGG metadata min–max player range (minplayers / maxplayers)."""
        metadata = obj.metadata
        if metadata is None:
            return "—"
        return _range_label(metadata.minplayers, metadata.maxplayers)

    @admin.display(description="Community")
    def community_player_labels(self, obj: BoardGame) -> str:
        """Show only the player-count range from BGG's recommendation summary."""
        return _community_labels(obj)

    @admin.display(description="Best")
    def best_player_labels(self, obj: BoardGame) -> str:
        """Show only the player-count range from BGG's best-player summary."""
        return _best_labels(obj)


def _player_count_summary_label(value: object) -> str:
    """Reduce BGG summary text to a compact player count/range."""
    if not isinstance(value, str):
        return "—"
    match = re.search(r"\d+(?:\s*[–—-]\s*\d+|\+)?", value)
    if match is None:
        return "—"
    return re.sub(r"\s*[–—]\s*", "-", match.group())


def _community_labels(obj: BoardGame) -> str:
    """Display recommendedwith text from poll summary (Packet 4)."""
    meta = getattr(obj, "metadata", None)
    if meta is None:
        return "—"
    summary = getattr(meta, "numplayers_summary", None)
    if not summary or not isinstance(summary, Mapping):
        return "—"
    return _player_count_summary_label(summary.get("recommendedwith"))


def _best_labels(obj: BoardGame) -> str:
    """Display bestwith text from poll summary (Packet 4)."""
    meta = getattr(obj, "metadata", None)
    if meta is None:
        return "—"
    summary = getattr(meta, "numplayers_summary", None)
    if not summary or not isinstance(summary, Mapping):
        return "—"
    return _player_count_summary_label(summary.get("bestwith"))


def _labels_with_votes(label: str, tied_labels: list[str], max_val: int) -> str:
    """Join tied numplayers labels; append vote count when concise."""
    joined = ", ".join(tied_labels)
    if max_val > 0 and max_val <= 999:
        return f"{joined} ({max_val})"
    return joined


# ------------------------------------------------------------------ #
# BGGMetadataAdmin (unchanged from previous packets)
# ------------------------------------------------------------------ #


class BGGMetadataAdmin(admin.ModelAdmin):
    """Read-only admin for canonical BGG metadata."""

    list_display = [
        "bgg_id",
        "name",
        "yearpublished",
        "collection_plays",
    ]
    list_filter = [
        "yearpublished",
    ]
    search_fields = [
        "bgg_id",
        "name",
    ]
    readonly_fields = [
        "bgg_id",
        "name",
        "yearpublished",
        "minplayers",
        "maxplayers",
        "playingtime",
        "comment",
        "thumbnail",
        "image",
        "publishers",
        "designers",
        "mechanics",
        "categories",
        "alternative_names",
        "bgg_rank",
        "bgg_url",
        "boardgame_rank",
        "families",
        "item_type",
        "min_playing_time",
        "max_playing_time",
        "rating_bayes_average",
        "rating_average",
        "rating_median",
        "rating_stddev",
        "rating_num_weights",
        "users_rated",
        "users_owned",
        "collection_plays",
        "suggested_players",
        "numplayers_summary",
    ]
    exclude = ["plays_count"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("collection_observation")

    @admin.display(
        description="Your BGG plays", ordering="collection_observation__numplays"
    )
    def collection_plays(self, obj: BGGMetadata) -> int | str:
        observation = getattr(obj, "collection_observation", None)
        if observation is None or observation.numplays is None:
            return "—"
        return int(observation.numplays)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ------------------------------------------------------------------ #
# BGGExpansionAdmin (unchanged)
# ------------------------------------------------------------------ #


class BGGExpansionAdmin(admin.ModelAdmin):
    """Read-only admin for expansion relationships."""

    list_display = [
        "expansion_link",
        "parent_link",
        "exp_type",
        "order",
    ]
    list_filter = [
        "exp_type",
    ]
    search_fields = [
        "expansion__bgg_id",
        "expansion__name",
        "parent__bgg_id",
        "parent__name",
    ]
    readonly_fields = [
        "expansion_link",
        "parent_link",
        "exp_type",
        "order",
    ]
    fields = ("expansion_link", "parent_link", "exp_type", "order")

    def get_queryset(self, request):
        copies = BoardGame.objects.filter(removed=False).order_by("imported", "id")
        return (
            super()
            .get_queryset(request)
            .select_related("expansion", "parent")
            .prefetch_related(
                Prefetch(
                    "expansion__copies",
                    queryset=copies,
                    to_attr="admin_active_copies",
                ),
                Prefetch(
                    "parent__copies",
                    queryset=copies,
                    to_attr="admin_active_copies",
                ),
            )
        )

    @admin.display(description="Expansion", ordering="expansion__name")
    def expansion_link(self, obj: BGGExpansion):
        return _metadata_destination(obj.expansion)

    @admin.display(description="Parent game", ordering="parent__name")
    def parent_link(self, obj: BGGExpansion):
        return _metadata_destination(obj.parent)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ------------------------------------------------------------------ #
# BGGSyncRunAdmin (unchanged)
# ------------------------------------------------------------------ #


class BGGSyncRunAdmin(admin.ModelAdmin):
    """Read-only admin for synchronization diagnostics."""

    list_display = [
        "pk",
        "status",
        "fetch_successful",
        "items_total",
        "items_fetched",
        "items_failed",
        "created_at",
    ]
    list_filter = [
        "status",
        "fetch_successful",
    ]
    search_fields = [
        "error_messages",
        "diagnostics",
    ]
    readonly_fields = [
        "status",
        "fetch_successful",
        "items_total",
        "items_fetched",
        "items_failed",
        "error_messages",
        "diagnostics",
        "created_at",
        "completed_at",
    ]
    exclude = []

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# Register all four models (idempotent against double-registration).
admin.site.register(BoardGame, BoardGameAdmin)
admin.site.register(BGGMetadata, BGGMetadataAdmin)
admin.site.register(BGGExpansion, BGGExpansionAdmin)
admin.site.register(BGGSyncRun, BGGSyncRunAdmin)


def _bgg_url(metadata: BGGMetadata) -> str:
    """Return a usable BGG page URL even when the payload omits objecturl."""

    return metadata.bgg_url or f"https://boardgamegeek.com/boardgame/{metadata.bgg_id}"
