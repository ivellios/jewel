from django.urls import path

from .views import (
    GameDetailAPIView,
    GameListCreateAPIView,
    GamePlatformCreateAPIView,
    GamePlatformDetailAPIView,
    PlatformListCreateAPIView,
    VendorListAPIView,
)

urlpatterns = [
    path("games/", GameListCreateAPIView.as_view(), name="game-list-create-api"),
    path("games/<uuid:id>/", GameDetailAPIView.as_view(), name="game-detail-api"),
    path(
        "games/<uuid:game_id>/platforms/",
        GamePlatformCreateAPIView.as_view(),
        name="game-platform-create-api",
    ),
    path(
        "games/<uuid:game_id>/platforms/<int:platform_id>/",
        GamePlatformDetailAPIView.as_view(),
        name="game-platform-detail-api",
    ),
    path(
        "platforms/",
        PlatformListCreateAPIView.as_view(),
        name="platform-list-create-api",
    ),
    path("vendors/", VendorListAPIView.as_view(), name="vendor-list-api"),
]
