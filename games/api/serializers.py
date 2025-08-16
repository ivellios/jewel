from rest_framework import serializers
from django.utils import timezone
from ..models import Game, Platform, Genre, GameOnPlatform, Vendor


class PlatformSerializer(serializers.ModelSerializer):
    class Meta:
        model = Platform
        fields = ["id", "name"]

    def validate_name(self, value):
        return value.strip() if value else value


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ["id", "name"]

    def validate_name(self, value):
        return value.strip() if value else value


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ["id", "name"]

    def validate_name(self, value):
        return value.strip() if value else value


class GameOnPlatformSerializer(serializers.ModelSerializer):
    platform = PlatformSerializer(read_only=True)
    source = VendorSerializer(read_only=True)

    class Meta:
        model = GameOnPlatform
        fields = ["platform", "added", "identifier", "price", "source"]


class GameSerializer(serializers.ModelSerializer):
    platforms_meta_data = GameOnPlatformSerializer(many=True, read_only=True)
    genres = GenreSerializer(many=True, read_only=True)

    class Meta:
        model = Game
        fields = [
            "id",
            "title",
            "play_priority",
            "played",
            "controller_support",
            "max_players",
            "party_fit",
            "review",
            "notes",
            "genres",
            "platforms_meta_data",
        ]


class GameCreateSerializer(serializers.ModelSerializer):
    platform_id = serializers.IntegerField(write_only=True)
    vendor_id = serializers.IntegerField(write_only=True)
    added = serializers.DateField(required=False, write_only=True)
    price = serializers.DecimalField(max_digits=6, decimal_places=2, write_only=True)

    class Meta:
        model = Game
        fields = [
            "title",
            "platform_id",
            "vendor_id",
            "added",
            "price",
            "play_priority",
            "played",
            "controller_support",
            "max_players",
            "party_fit",
            "review",
            "notes",
        ]

    def validate_title(self, value):
        return value.strip() if value else value

    def validate_notes(self, value):
        return value.strip() if value else value

    def validate_platform_id(self, value):
        try:
            Platform.objects.get(id=value)
        except Platform.DoesNotExist:
            raise serializers.ValidationError("Platform with this ID does not exist.")
        return value

    def validate_vendor_id(self, value):
        try:
            Vendor.objects.get(id=value)
        except Vendor.DoesNotExist:
            raise serializers.ValidationError("Vendor with this ID does not exist.")
        return value

    def create(self, validated_data):
        platform_id = validated_data.pop("platform_id")
        vendor_id = validated_data.pop("vendor_id")
        added = validated_data.pop("added", timezone.now().date())
        price = validated_data.pop("price")

        # Create the game
        game = Game.objects.create(**validated_data)

        # Create the GameOnPlatform relationship
        GameOnPlatform.objects.create(
            game=game,
            platform_id=platform_id,
            source_id=vendor_id,
            added=added,
            price=price,
        )

        return game
