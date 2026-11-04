"""BoardGame API views with authentication and read-only source fields."""

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

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

    def destroy(self, request, *args, **kwargs):
        """BGG-sourced items use reversible removal; local-only items are physically deleted."""
        instance = self.get_object()
        if instance.imported:
            # Source-managed: use reversible removal (soft delete).
            instance.removed = True
            instance.owned = False
            instance.save(update_fields=["removed", "owned"])
            return Response(status=status.HTTP_200_OK)
        # Local-only: physical deletion is safe (no source to corrupt).
        return super().destroy(request, *args, **kwargs)
