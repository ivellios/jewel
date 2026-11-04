"""Safe Django admin surfaces for the boardgames app.

BoardGame: editable local fields (name, language, edition_label, condition,
storage, purchase_date, inherited CollectionItem fields); read-only
source/ownership/state fields (metadata, imported, owned, removed).

BGGMetadata: read-only source metadata — BGG-owned fields only.

BGGExpansion: read-only relationship data — derived from BGG.

BGGSyncRun: read-only diagnostic records — run lifecycle, counters, errors.
"""

from django.contrib import admin
from django.utils.html import format_html

from boardgames.models import (
    BGGExpansion,
    BGGMetadata,
    BGGSyncRun,
    BoardGame,
)


def _state_label(value: bool) -> str:
    """Human-readable state label."""
    return "Imported" if value else "Local"


# ------------------------------------------------------------------ #
# BoardGameAdmin
# ------------------------------------------------------------------ #


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
        "state",
        "imported",
        "owned",
        "removed",
        "language",
    ]
    list_filter = [
        "imported",
        "owned",
        "removed",
        "metadata",
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
                    "metadata",
                    "imported",
                    "owned",
                    "removed",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    # Source/ownership/state fields: read-only, visible for reference.
    readonly_fields = [
        "metadata",
        "imported",
        "owned",
        "removed",
        "metadata_link",
        "state",
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

    @admin.display(description="BGG Source")
    def metadata_link(self, obj: BoardGame):
        if obj.metadata_id:
            url = obj.metadata.bgg_url or ""
            return format_html(
                '<a href="{url}" target="_blank" rel="noopener">BGG #{bgg_id}</a>',
                url=url,
                bgg_id=obj.metadata.bgg_id,
            )
        return "— (local-only)"

    @admin.display(description="State")
    def state(self, obj: BoardGame) -> str:
        """Show local vs. imported state at a glance."""
        if obj.imported:
            return format_html(
                '<span style="color: #0a0;">{label}</span>', label="Imported"
            )
        return format_html(
            '<span style="color: #666;">{label}</span>', label="Local-only"
        )


# ------------------------------------------------------------------ #
# BGGMetadataAdmin (unchanged from previous packets)
# ------------------------------------------------------------------ #


class BGGMetadataAdmin(admin.ModelAdmin):
    """Read-only admin for canonical BGG metadata."""

    list_display = [
        "bgg_id",
        "name",
        "yearpublished",
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
        "plays_count",
    ]
    exclude = []

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
        "expansion",
        "parent",
        "exp_type",
        "order",
    ]
    list_filter = [
        "exp_type",
    ]
    search_fields = [
        "expansion__bgg_id",
        "parent__bgg_id",
    ]
    readonly_fields = [
        "expansion",
        "parent",
        "exp_type",
        "order",
    ]

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
