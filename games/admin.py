from datetime import date, timedelta

from django.contrib import admin
from django.db import models
from django.db.models import Count, Q
from django.urls import path, reverse
from django.utils.formats import localize

from games.admin_views.bulk_import import bulk_import_view
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


class LatestAddedFilter(admin.SimpleListFilter):
    title = "latest added date"
    parameter_name = "latest_added_filter"

    def lookups(self, request, model_admin):
        return (
            ("today", "Today"),
            ("week", "Past 7 days"),
            ("month", "Past 30 days"),
            ("never", "Never added"),
        )

    def queryset(self, request, queryset):
        today = date.today()

        if self.value() == "today":
            return queryset.filter(latest_added=today)
        elif self.value() == "week":
            return queryset.filter(latest_added__gte=today - timedelta(days=7))
        elif self.value() == "month":
            return queryset.filter(latest_added__gte=today - timedelta(days=30))
        elif self.value() == "never":
            return queryset.filter(latest_added__isnull=True)
        return queryset


class WithDateFilter(admin.SimpleListFilter):
    title = "With adding date only"
    parameter_name = "with_date"

    def lookups(self, request, model_admin):
        return (("with_date", "With adding date only"),)

    def queryset(self, request, queryset):
        if self.value() == "with_date":
            return queryset.filter(platforms_meta_data__added__isnull=False).distinct()
        return queryset


class VendorFilter(admin.SimpleListFilter):
    title = "vendor"
    parameter_name = "vendor_filter"

    def lookups(self, request, model_admin):
        # Get vendors that have active GameOnPlatform relationships
        vendors = (
            Vendor.objects.filter(gameonplatform__deleted=False)
            .distinct()
            .order_by("name")
        )
        return [(vendor.id, vendor.name) for vendor in vendors]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                platforms_meta_data__vendor_id=self.value(),
                platforms_meta_data__deleted=False,
            ).distinct()
        return queryset


class GameAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "active_platforms",
        "play_priority",
        "played",
        "controller_support",
        "max_players",
        "party_fit",
        "review",
        "notes",
        "total_price_paid",
        "latest_added_date",
        "vendors_list",
    ]
    list_filter = [
        GameStatusFilter,
        LatestAddedFilter,
        WithDateFilter,
        VendorFilter,
        "play_priority",
        "played",
        "controller_support",
        "max_players",
        "party_fit",
        "platforms",
        "genres",
    ]
    # ordering = [
    #     "-latest_added_date",
    # ]
    search_fields = [
        "name",
    ]
    inlines = (GameOnPlatformInline,)

    def get_queryset(self, request):
        # Use all_with_orphaned to show both active and orphaned games
        return (
            Game.objects.all_with_orphaned()
            .annotate(
                active_platform_count=Count(
                    "platforms_meta_data", filter=Q(platforms_meta_data__deleted=False)
                ),
                latest_added=models.Max("platforms_meta_data__added"),
                total_price=models.Sum("platforms_meta_data__price"),
            )
            .order_by("-latest_added")
        )

    def active_platforms(self, obj):
        active_platforms = obj.platforms_meta_data.filter(deleted=False).select_related(
            "platform"
        )
        platform_names = [gop.platform.name for gop in active_platforms]
        return ", ".join(platform_names) if platform_names else "None"

    active_platforms.short_description = "Active Platforms"

    def vendors_list(self, obj):
        vendors = obj.platforms_meta_data.filter(deleted=False).select_related("vendor")
        vendor_names = {gop.vendor.name for gop in vendors if gop.vendor}
        return ", ".join(sorted(vendor_names)) if vendor_names else "None"

    vendors_list.short_description = "Vendors"

    def total_price_paid(self, obj):
        if obj.total_price is not None:
            return localize(obj.total_price)
        return localize(0)

    total_price_paid.short_description = "Total Paid"
    total_price_paid.admin_order_field = "total_price"

    def latest_added_date(self, obj):
        return obj.latest_added if obj.latest_added else "Never"

    latest_added_date.short_description = "Latest Added"
    latest_added_date.admin_order_field = "latest_added"

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

    def get_urls(self):
        """Add custom URL for bulk import"""
        urls = super().get_urls()
        custom_urls = [
            path(
                "bulk_import/",
                self.admin_site.admin_view(self.bulk_import_games),
                name="games_game_bulk_import",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        """Add bulk import button to changelist view"""
        extra_context = extra_context or {}
        extra_context["bulk_import_url"] = reverse("admin:games_game_bulk_import")
        return super().changelist_view(request, extra_context)

    def bulk_import_games(self, request):
        """Custom admin view for bulk importing games (delegates to standalone view)"""
        return bulk_import_view(request)


admin.site.register(Game, GameAdmin)
admin.site.register(Platform)
admin.site.register(Vendor)
admin.site.register(Genre)
