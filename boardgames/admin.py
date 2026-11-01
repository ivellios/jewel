"""Safe Django admin surfaces for the boardgames app.

BoardGame: editable local fields (name, language, edition_label);
read-only source/ownership/state fields (metadata, imported, owned, removed).

BGGMetadata: read-only source metadata — BGG-owned fields only.

BGGExpansion: read-only relationship data — derived from BGG.

BGGSyncRun: read-only diagnostic records — run lifecycle, counters, errors.
"""

from django.contrib import admin

from boardgames.models import (
    BGGExpansion,
    BGGMetadata,
    BGGSyncRun,
    BoardGame,
)


class BoardGameAdmin(admin.ModelAdmin):
    """Board game copy admin: editable local fields, read-only source/ownership."""

    list_display = [
        "display_name",
        "metadata",
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
    # Local fields that are editable.
    fields = [
        "name",
        "language",
        "edition_label",
        "condition",
        "storage",
        "purchase_date",
    ]
    # Source/ownership/state fields: read-only, visible for reference.
    readonly_fields = [
        "metadata",
        "imported",
        "owned",
        "removed",
    ]

    @admin.display(description="Name")
    def display_name(self, obj: BoardGame) -> str:
        return obj.display_name


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
    ]
    # Disable adding/editing entirely: this is source-of-truth data.
    exclude = []

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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
    # No editing: sync runs are append-only diagnostic records.
    exclude = []

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# Register all four models.
admin.site.register(BoardGame, BoardGameAdmin)
admin.site.register(BGGMetadata, BGGMetadataAdmin)
admin.site.register(BGGExpansion, BGGExpansionAdmin)
admin.site.register(BGGSyncRun, BGGSyncRunAdmin)
