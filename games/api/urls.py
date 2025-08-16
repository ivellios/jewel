from django.urls import path
from .views import GameListAPIView, GameDetailAPIView

urlpatterns = [
    path("", GameListAPIView.as_view(), name="game-list-api"),
    path("<uuid:id>/", GameDetailAPIView.as_view(), name="game-detail-api"),
]
