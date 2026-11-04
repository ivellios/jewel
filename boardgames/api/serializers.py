"""BoardGame API serializers with read-only source/sync/canonical fields."""

from rest_framework import serializers
from rest_framework.fields import SerializerMethodField

from ..models import (
    BGGCollectionObservation,
    BGGMetadata,
    BoardGame,
)


class BGGMetadataReadOnlySerializer(serializers.ModelSerializer):
    """Read-only canonical BGG metadata exposed in BoardGame responses."""

    class Meta:
        model = BGGMetadata
        fields = [
            "bgg_id",
            "name",
            "yearpublished",
            "minplayers",
            "maxplayers",
            "playingtime",
            "rating_bayes_average",
            "bgg_rank",
            "bgg_url",
            "thumbnail",
            "image",
        ]


class BGGCollectionObservationReadOnlySerializer(serializers.ModelSerializer):
    """Read-only BGG collection observation exposed in BoardGame responses."""

    class Meta:
        model = BGGCollectionObservation
        fields = [
            "quantity",
            "rating",
            "numplays",
            "owned",
            "prev_owned",
            "wishlist",
            "want",
            "want_to_play",
            "comment",
            "last_modified",
        ]


class BoardGameSerializer(serializers.ModelSerializer):
    """Full read serializer exposing all BoardGame fields plus nested source."""

    metadata = BGGMetadataReadOnlySerializer(read_only=True)
    collection_observation = SerializerMethodField()

    class Meta:
        model = BoardGame
        fields = [
            "id",
            "name",
            "metadata",
            "collection_observation",
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

    def get_collection_observation(self, obj):
        if obj.metadata_id is None:
            return None
        try:
            obs = obj.metadata.collection_observation
            return BGGCollectionObservationReadOnlySerializer(obs).data
        except BGGCollectionObservation.DoesNotExist:
            return None


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
