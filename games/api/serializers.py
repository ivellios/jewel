from django.utils import timezone

from rest_framework import serializers

from ..models import Game, GameOnPlatform, Genre, Platform, Vendor


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
            "name",
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
    platform_name = serializers.CharField(max_length=100, write_only=True)
    vendor_name = serializers.CharField(max_length=100, write_only=True)
    added = serializers.DateField(required=False, write_only=True)
    price = serializers.DecimalField(max_digits=6, decimal_places=2, write_only=True)

    class Meta:
        model = Game
        fields = [
            "name",
            "platform_name",
            "vendor_name",
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

    def validate_name(self, value):
        return value.strip() if value else value

    def validate_notes(self, value):
        return value.strip() if value else value

    def validate_platform_name(self, value):
        return value.strip() if value else value

    def validate_vendor_name(self, value):
        return value.strip() if value else value

    def create(self, validated_data):
        platform_name = validated_data.pop("platform_name")
        vendor_name = validated_data.pop("vendor_name")
        added = validated_data.pop("added", timezone.now().date())
        price = validated_data.pop("price")

        # Get or create platform with case-insensitive lookup
        platform = Platform.objects.filter(name__iexact=platform_name).first()
        if not platform:
            platform = Platform.objects.create(name=platform_name)

        # Get or create vendor with case-insensitive lookup
        vendor = Vendor.objects.filter(name__iexact=vendor_name).first()
        if not vendor:
            vendor = Vendor.objects.create(name=vendor_name)

        # Create the game
        game = Game.objects.create(**validated_data)

        # Create the GameOnPlatform relationship
        GameOnPlatform.objects.create(
            game=game,
            platform=platform,
            source=vendor,
            added=added,
            price=price,
        )

        return game
