from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from games.forms import BulkGameImportForm, GameImportFormSet
from games.models import Game, GameOnPlatform, Platform


def bulk_import_view(request):
    """Standalone view for bulk importing games"""
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
                "opts": Game._meta,
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
                global_platform = Platform.objects.get(id=global_platform_id)
            except Platform.DoesNotExist:
                global_platform = None

        formset = GameImportFormSet(request.POST, global_platform=global_platform)

        if form.is_valid() and formset.is_valid():
            return process_bulk_import(request, form, formset)
        else:
            # Re-render form with errors
            return render(
                request,
                "admin/games/game/bulk_import.html",
                {
                    "form": form,
                    "formset": formset,
                    "title": "Bulk Import Games",
                    "opts": Game._meta,
                    "has_change_permission": True,
                },
            )


@transaction.atomic
def process_bulk_import(request, form, formset):
    """Process the validated bulk import form"""
    # Get form data
    vendor = form.cleaned_data["vendor"]
    bundle_date = form.cleaned_data["bundle_date"]
    bundle_price = form.cleaned_data["bundle_price"]
    global_platform = form.cleaned_data.get("global_platform")
    global_notes = form.cleaned_data.get("global_notes", "").strip() or None

    # Collect all games to import
    games_to_import = []
    duplicates = []

    # Get games from detailed formset
    for game_data in formset.get_valid_games():
        game_name = game_data["game_name"].strip()
        # Use specific platform if provided, otherwise fallback to global_platform
        platform = game_data["platform"] or global_platform
        play_priority = game_data.get("play_priority")
        # Use individual notes if provided and not empty, otherwise use global notes
        individual_notes = game_data.get("notes", "").strip() or None
        notes = individual_notes if individual_notes else global_notes

        if not platform:
            # Skip games without any platform (should be caught by validation)
            continue

        games_to_import.append(
            {
                "name": game_name,
                "platform": platform,
                "play_priority": play_priority,
                "notes": notes,
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
                    "notes": global_notes,
                }
            )

    # Check for duplicates
    new_games_on_platforms = []
    for game_data in games_to_import:
        if GameOnPlatform.objects.filter(
            game__name__iexact=game_data["name"], platform_id=game_data["platform"]
        ).exists():
            duplicates.append(game_data["name"])
        else:
            new_games_on_platforms.append(game_data)

    if not new_games_on_platforms:
        messages.warning(request, "No new games to import - all games already exist.")
        return HttpResponseRedirect(reverse("admin:games_game_changelist"))

    # Calculate price per game (excluding duplicates)
    if bundle_price == 0 or len(new_games_on_platforms) == 0:
        price_per_game = Decimal("0.00")
    else:
        price_per_game = bundle_price / len(new_games_on_platforms)
        price_per_game = price_per_game.quantize(Decimal("0.01"))

    # Create games and platform relationships
    created_games = []
    for game_data in new_games_on_platforms:
        # Create game
        try:
            game = Game.objects.get(name__iexact=game_data["name"])
        except Game.DoesNotExist:
            game = Game.objects.create(
                name=game_data["name"],
                play_priority=game_data["play_priority"],
                notes=game_data["notes"],
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
