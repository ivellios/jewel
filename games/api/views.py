from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter
from ..models import Game
from .serializers import GameSerializer
from .authentication import APITokenAuthentication


class GameListAPIView(generics.ListAPIView):
    queryset = Game.objects.all()
    serializer_class = GameSerializer
    authentication_classes = [APITokenAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ["title"]


class GameDetailAPIView(generics.RetrieveAPIView):
    queryset = Game.objects.all()
    serializer_class = GameSerializer
    lookup_field = "id"
    authentication_classes = [APITokenAuthentication]
    permission_classes = [IsAuthenticated]
