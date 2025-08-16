from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from ..models import Game
from .serializers import GameSerializer
from .authentication import APITokenAuthentication


class GameDetailAPIView(generics.RetrieveAPIView):
    queryset = Game.objects.all()
    serializer_class = GameSerializer
    lookup_field = 'id'
    authentication_classes = [APITokenAuthentication]
    permission_classes = [IsAuthenticated]