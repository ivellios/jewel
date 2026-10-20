from typing import Any

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import Vendor, VideoGame, VideoGameOnPlatform, VideoGamePlatform
from .filters import GameFilterSet
from .serializers import (
    GameCreateSerializer,
    GamePlatformCreateSerializer,
    GamePlatformUpdateSerializer,
    GameSerializer,
    GameUpdateSerializer,
    PlatformSerializer,
    VendorSerializer,
)


class PlatformListCreateAPIView(generics.ListCreateAPIView):
    queryset = VideoGamePlatform.objects.all()
    serializer_class = PlatformSerializer
    permission_classes = [IsAuthenticated]


class VendorListAPIView(generics.ListAPIView):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated]


class GameListCreateAPIView(generics.ListCreateAPIView):
    queryset = VideoGame.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = GameFilterSet

    def get_serializer_class(self):
        if self.request.method == "POST":
            return GameCreateSerializer
        return GameSerializer


class GameDetailAPIView(generics.RetrieveUpdateAPIView):
    queryset = VideoGame.objects.all()
    lookup_field = "id"
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return GameUpdateSerializer
        return GameSerializer


class GamePlatformCreateAPIView(generics.CreateAPIView):
    serializer_class = GamePlatformCreateSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context: dict[str, Any] = dict(super().get_serializer_context())
        try:
            game = VideoGame.objects.get(id=self.kwargs["game_id"])
            context["game"] = game
        except VideoGame.DoesNotExist:
            context["game"] = None
        return context


class GamePlatformDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = GamePlatformUpdateSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        try:
            game = VideoGame.objects.get(id=self.kwargs["game_id"])
            platform = VideoGamePlatform.objects.get(id=self.kwargs["platform_id"])
            return VideoGameOnPlatform.objects.get(
                game=game, platform=platform, deleted=False
            )
        except (
            VideoGame.DoesNotExist,
            VideoGamePlatform.DoesNotExist,
            VideoGameOnPlatform.DoesNotExist,
        ):
            return None

    def put(self, request, game_id, platform_id):
        game_platform = self.get_object()
        if not game_platform:
            return Response(
                {"error": "Game-platform relationship not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = GamePlatformUpdateSerializer(game_platform, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Game-platform relationship updated successfully",
                "platform_name": game_platform.platform.name,
            }
        )

    def patch(self, request, game_id, platform_id):
        game_platform = self.get_object()
        if not game_platform:
            return Response(
                {"error": "Game-platform relationship not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = GamePlatformUpdateSerializer(
            game_platform, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Game-platform relationship updated successfully",
                "platform_name": game_platform.platform.name,
            }
        )

    def delete(self, request, game_id, platform_id):
        game_platform = self.get_object()
        if not game_platform:
            return Response(
                {"error": "Game-platform relationship not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        platform_name = game_platform.platform.name
        game_platform.soft_delete()

        return Response(
            {"message": f"Platform '{platform_name}' removed from game successfully"},
            status=status.HTTP_200_OK,
        )
