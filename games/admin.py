from django.contrib import admin
from django.db.models import Count, Q

from games.models import Game, GameOnPlatform, Genre, Platform, Vendor

# Register your models here.


class GameOnPlatformInline(admin.TabularInline):
    model = Game.platforms.through
    fields = [
        "platform",
        "vendor",
        "added",
        "identifier",
        "price",
        "deleted",
        "deleted_at",
    ]
    readonly_fields = ["deleted_at"]
    extra = 1


class GameStatusFilter(admin.SimpleListFilter):
    title = "game status"
    parameter_name = "game_status"

    def lookups(self, request, model_admin):
        return (
            ("active", "Games with active platforms"),
            ("orphaned", "Orphaned games (no active platforms)"),
        )

    def queryset(self, request, queryset):
        if self.value() == "active":
            return queryset.filter(platforms_meta_data__deleted=False).distinct()
        elif self.value() == "orphaned":
            return queryset.exclude(platforms_meta_data__deleted=False)
        return queryset


class GameAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "play_priority",
        "played",
        "controller_support",
        "max_players",
        "party_fit",
        "review",
        "notes",
        "active_platforms",
        "is_orphaned",
    ]
    list_filter = [
        GameStatusFilter,
        "play_priority",
        "played",
        "controller_support",
        "max_players",
        "party_fit",
        "platforms",
        "genres",
    ]
    search_fields = [
        "name",
    ]
    inlines = (GameOnPlatformInline,)

    def get_queryset(self, request):
        # Use all_with_orphaned to show both active and orphaned games
        return Game.objects.all_with_orphaned().annotate(
            active_platform_count=Count(
                "platforms_meta_data", filter=Q(platforms_meta_data__deleted=False)
            )
        )

    def active_platforms(self, obj):
        active_platforms = obj.platforms_meta_data.filter(deleted=False).select_related(
            "platform"
        )
        platform_names = [gop.platform.name for gop in active_platforms]
        return ", ".join(platform_names) if platform_names else "None"

    active_platforms.short_description = "Active Platforms"

    def is_orphaned(self, obj):
        return obj.active_platform_count == 0

    is_orphaned.boolean = True
    is_orphaned.short_description = "Orphaned"
    is_orphaned.admin_order_field = "active_platform_count"

    actions = ["restore_all_platforms", "make_orphaned"]

    def restore_all_platforms(self, request, queryset):
        count = 0
        for game in queryset:
            restored = GameOnPlatform.objects.filter(game=game, deleted=True).update(
                deleted=False, deleted_at=None
            )
            count += restored
        self.message_user(request, f"Restored {count} platform relationships.")

    restore_all_platforms.short_description = "Restore all platforms for selected games"

    def make_orphaned(self, request, queryset):
        count = 0
        for game in queryset:
            platforms = GameOnPlatform.objects.filter(game=game, deleted=False)
            for platform in platforms:
                platform.soft_delete()
                count += 1
        self.message_user(request, f"Soft-deleted {count} platform relationships.")

    make_orphaned.short_description = "Remove all platforms from selected games"


admin.site.register(Game, GameAdmin)
admin.site.register(Platform)
admin.site.register(Vendor)
admin.site.register(Genre)
