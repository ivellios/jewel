from decimal import Decimal

from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse

from games.forms import BulkGameImportForm, GameImportFormSet
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
        """Custom admin view for bulk importing games"""
        if request.method == "GET":
            # Show the form
            form = BulkGameImportForm()
            formset = GameImportFormSet()
            return render(
                request,
                "admin/games/game/bulk_import.html",
                {
                    "form": form,
                    "formset": formset,
                    "title": "Bulk Import Games",
                    "opts": self.model._meta,
                    "has_change_permission": True,
                },
            )

        elif request.method == "POST":
            # Process the form
            form = BulkGameImportForm(request.POST)

            # Pass global_platform to formset for validation
            # We need to get the global_platform even from partial form data for validation
            global_platform_id = request.POST.get("global_platform")
            global_platform = None
            if global_platform_id:
                try:
                    from games.models import Platform

                    global_platform = Platform.objects.get(id=global_platform_id)
                except Platform.DoesNotExist:
                    pass

            formset = GameImportFormSet(request.POST, global_platform=global_platform)

            if form.is_valid() and formset.is_valid():
                return self._process_bulk_import(request, form, formset)
            else:
                # Re-render form with errors
                return render(
                    request,
                    "admin/games/game/bulk_import.html",
                    {
                        "form": form,
                        "formset": formset,
                        "title": "Bulk Import Games",
                        "opts": self.model._meta,
                        "has_change_permission": True,
                    },
                )

    @transaction.atomic
    def _process_bulk_import(self, request, form, formset):
        """Process the validated bulk import form"""
        # Get form data
        vendor = form.cleaned_data["vendor"]
        bundle_date = form.cleaned_data["bundle_date"]
        bundle_price = form.cleaned_data["bundle_price"]
        global_platform = form.cleaned_data.get("global_platform")

        # Collect all games to import
        games_to_import = []
        duplicates = []

        # Get games from detailed formset
        for game_data in formset.get_valid_games():
            game_name = game_data["game_name"].strip()
            # Use specific platform if provided, otherwise fallback to global_platform
            platform = game_data["platform"] or global_platform
            play_priority = game_data.get("play_priority")

            if not platform:
                # Skip games without any platform (should be caught by validation)
                continue

            games_to_import.append(
                {
                    "name": game_name,
                    "platform": platform,
                    "play_priority": play_priority,
                }
            )

        # Get games from quick input
        quick_games_list = form.get_quick_games_list()
        if quick_games_list:
            # Quick games always use global_platform (validation ensures it's set)
            for game_name in quick_games_list:
                games_to_import.append(
                    {
                        "name": game_name,
                        "platform": global_platform,
                        "play_priority": None,
                    }
                )

        # Check for duplicates
        new_games = []
        for game_data in games_to_import:
            if Game.objects.filter(name__iexact=game_data["name"]).exists():
                duplicates.append(game_data["name"])
            else:
                new_games.append(game_data)

        if not new_games:
            messages.warning(
                request, "No new games to import - all games already exist."
            )
            return HttpResponseRedirect(reverse("admin:games_game_changelist"))

        # Calculate price per game (excluding duplicates)
        if bundle_price == 0 or len(new_games) == 0:
            price_per_game = Decimal("0.00")
        else:
            price_per_game = bundle_price / len(new_games)
            price_per_game = price_per_game.quantize(Decimal("0.01"))

        # Create games and platform relationships
        created_games = []
        for game_data in new_games:
            # Create game
            game = Game.objects.create(
                name=game_data["name"], play_priority=game_data["play_priority"]
            )

            # Create platform relationship
            GameOnPlatform.objects.create(
                game=game,
                platform=game_data["platform"],
                vendor=vendor,
                added=bundle_date,
                price=price_per_game,
            )

            created_games.append(game)

        # Show success message with statistics
        success_msg = f"Successfully imported {len(created_games)} games"
        if duplicates:
            success_msg += (
                f". Skipped {len(duplicates)} duplicates: {', '.join(duplicates[:5])}"
            )
            if len(duplicates) > 5:
                success_msg += f" (and {len(duplicates) - 5} more)"

        messages.success(request, success_msg)
        return HttpResponseRedirect(reverse("admin:games_game_changelist"))


admin.site.register(Game, GameAdmin)
admin.site.register(Platform)
admin.site.register(Vendor)
admin.site.register(Genre)
