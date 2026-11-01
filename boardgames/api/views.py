"""BoardGame API views with authentication and read-only source fields."""

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from ..models import BoardGame
from .serializers import (
    BoardGameCreateSerializer,
    BoardGameSerializer,
    BoardGameUpdateSerializer,
)


class BoardGameListCreateAPIView(generics.ListCreateAPIView):
    queryset = BoardGame.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return BoardGameCreateSerializer
        return BoardGameSerializer


class BoardGameDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = BoardGame.objects.all()
    lookup_field = "id"
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return BoardGameUpdateSerializer
        return BoardGameSerializer
