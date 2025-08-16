from django.contrib import admin

from games.models import Game, Genre, Platform, Vendor

# Register your models here.


class GameOnPlatformInline(admin.TabularInline):
    model = Game.platforms.through
    extra = 1


class GameAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "play_priority",
        "played",
        "controller_support",
        "max_players",
        "party_fit",
        "review",
        "notes",
    ]
    list_filter = [
        "play_priority",
        "played",
        "controller_support",
        "max_players",
        "party_fit",
        "platforms",
        "genres",
    ]
    search_fields = [
        "title",
    ]
    inlines = (GameOnPlatformInline,)


admin.site.register(Game, GameAdmin)
admin.site.register(Platform)
admin.site.register(Vendor)
admin.site.register(Genre)
