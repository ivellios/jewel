from django.contrib import admin

from steam.models import SteamGame

class SteamGameAdmin(admin.ModelAdmin):
    search_fields = [
        "name",
        "appid",
    ]

admin.site.register(SteamGame, SteamGameAdmin)
