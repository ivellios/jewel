from datetime import date
from decimal import Decimal

from django import forms
from django.forms import formsets

from games.models import Platform, Vendor


class BulkGameImportForm(forms.Form):
    """Main form for bulk game import containing bundle-level information"""

    vendor = forms.ModelChoiceField(
        queryset=Vendor.objects.all(),
        required=True,
        help_text="Select the vendor where this bundle was purchased",
    )

    bundle_date = forms.DateField(
        required=True,
        initial=date.today,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Date when the bundle was purchased",
    )

    bundle_price = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=True,
        min_value=Decimal("0.00"),
        help_text="Total price paid for the entire bundle (can be 0 for free bundles)",
    )

    global_platform = forms.ModelChoiceField(
        queryset=Platform.objects.all(),
        required=False,
        empty_label="-- No default platform --",
        help_text="Optional: Default platform for games without specific platform selected",
    )

    quick_games = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 3, "placeholder": "Enter game names separated by commas"}
        ),
        help_text="Quick input: Enter comma-separated game names. Will use Default Platform above.",
    )

    def clean(self):
        cleaned_data = super().clean()
        quick_games = cleaned_data.get("quick_games")
        global_platform = cleaned_data.get("global_platform")

        # If quick_games is provided, global_platform is required
        if quick_games and quick_games.strip() and not global_platform:
            raise forms.ValidationError(
                "Default Platform is required when using quick games input"
            )

        return cleaned_data

    def get_quick_games_list(self):
        """Parse quick_games field into a list of game names"""
        quick_games = self.cleaned_data.get("quick_games", "")
        if not quick_games or not quick_games.strip():
            return []

        # Split by comma and clean up names
        games = [name.strip() for name in quick_games.split(",")]
        return [name for name in games if name]  # Remove empty strings


class GameImportForm(forms.Form):
    """Form for individual game entry within the bulk import"""

    game_name = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Enter game name"}),
    )

    platform = forms.ModelChoiceField(
        queryset=Platform.objects.all(),
        required=False,
        help_text="Platform for this specific game",
    )

    play_priority = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=10,
        widget=forms.NumberInput(attrs={"min": 1, "max": 10, "placeholder": "1-10"}),
        help_text="Play priority (1-10, optional)",
    )

    def is_empty(self):
        """Check if this form represents an empty entry"""
        game_name = self.cleaned_data.get("game_name", "").strip()
        return not game_name


class GameImportFormSet(formsets.BaseFormSet):
    """Formset for handling multiple game entries"""

    def __init__(self, *args, **kwargs):
        self.global_platform = kwargs.pop("global_platform", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        """Validate the formset"""
        if any(self.errors):
            return

        # Check for duplicate game names within the formset
        game_names = []
        for form in self.forms:
            if hasattr(form, "cleaned_data") and not form.is_empty():
                game_name = form.cleaned_data.get("game_name", "").strip()

                if game_name:
                    if game_name in game_names:
                        raise forms.ValidationError(
                            f"Duplicate game name in forms: {game_name}"
                        )
                    game_names.append(game_name)

    def get_valid_games(self):
        """Get list of valid, non-empty games from the formset"""
        valid_games = []
        for form in self.forms:
            if (
                hasattr(form, "cleaned_data")
                and form.is_valid()
                and not form.is_empty()
            ):
                valid_games.append(form.cleaned_data)
        return valid_games


# Create the formset class
GameImportFormSet = formsets.formset_factory(
    GameImportForm,
    formset=GameImportFormSet,
    extra=5,  # Show 5 empty forms by default
    max_num=100,  # Maximum number of games in one import
    validate_max=True,
    can_delete=False,
)
