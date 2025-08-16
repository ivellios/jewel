from django.urls import path
from .views import (
    GameListCreateAPIView, 
    GameDetailAPIView, 
    PlatformListAPIView, 
    VendorListAPIView
)

urlpatterns = [
    path("games/", GameListCreateAPIView.as_view(), name="game-list-create-api"),
    path("games/<uuid:id>/", GameDetailAPIView.as_view(), name="game-detail-api"),
    path("platforms/", PlatformListAPIView.as_view(), name="platform-list-api"),
    path("vendors/", VendorListAPIView.as_view(), name="vendor-list-api"),
]
