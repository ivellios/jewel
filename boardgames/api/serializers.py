"""BoardGame API serializers with read-only source/sync/canonical fields."""

from rest_framework import serializers

from ..models import BoardGame


class BoardGameSerializer(serializers.ModelSerializer):
    """Full read serializer exposing all BoardGame fields."""

    class Meta:
        model = BoardGame
        fields = [
            "id",
            "name",
            "metadata",
            "language",
            "edition_label",
            "condition",
            "storage",
            "purchase_date",
            "imported",
            "owned",
            "removed",
            "played",
            "review",
            "notes",
            "play_priority",
            "min_players",
            "max_players",
        ]


class BoardGameCreateSerializer(serializers.ModelSerializer):
    """Writeable fields only for create operations."""

    class Meta:
        model = BoardGame
        fields = [
            "id",
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
        ]
        read_only_fields = ("id",)


class BoardGameUpdateSerializer(serializers.ModelSerializer):
    """Writeable fields only for update operations."""

    class Meta:
        model = BoardGame
        fields = [
            "id",
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
        ]
        read_only_fields = ("id",)
