from django.urls import path

from .views import (
    BoardGameDetailAPIView,
    BoardGameListCreateAPIView,
)

urlpatterns = [
    path(
        "",
        BoardGameListCreateAPIView.as_view(),
        name="boardgame-list-create-api",
    ),
    path(
        "<uuid:id>/",
        BoardGameDetailAPIView.as_view(),
        name="boardgame-detail-api",
    ),
]
