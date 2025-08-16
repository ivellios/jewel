from rest_framework import serializers
from ..models import Game, Platform, Genre, GameOnPlatform, Vendor


class PlatformSerializer(serializers.ModelSerializer):
    class Meta:
        model = Platform
        fields = ['id', 'name']


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ['id', 'name']


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ['id', 'name']


class GameOnPlatformSerializer(serializers.ModelSerializer):
    platform = PlatformSerializer(read_only=True)
    source = VendorSerializer(read_only=True)
    
    class Meta:
        model = GameOnPlatform
        fields = ['platform', 'added', 'identifier', 'price', 'source']


class GameSerializer(serializers.ModelSerializer):
    platforms_meta_data = GameOnPlatformSerializer(many=True, read_only=True)
    genres = GenreSerializer(many=True, read_only=True)
    
    class Meta:
        model = Game
        fields = [
            'id', 'title', 'play_priority', 'played', 'controller_support',
            'max_players', 'party_fit', 'review', 'notes', 'genres',
            'platforms_meta_data'
        ]