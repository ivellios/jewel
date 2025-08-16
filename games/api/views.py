from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter
from ..models import Game, Platform, Vendor
from .serializers import GameSerializer, PlatformSerializer, VendorSerializer, GameCreateSerializer
from .authentication import APITokenAuthentication


class PlatformListAPIView(generics.ListAPIView):
    queryset = Platform.objects.all()
    serializer_class = PlatformSerializer
    authentication_classes = [APITokenAuthentication]
    permission_classes = [IsAuthenticated]


class VendorListAPIView(generics.ListAPIView):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer
    authentication_classes = [APITokenAuthentication]
    permission_classes = [IsAuthenticated]


class GameListCreateAPIView(generics.ListCreateAPIView):
    queryset = Game.objects.all()
    authentication_classes = [APITokenAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ["title"]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return GameCreateSerializer
        return GameSerializer


class GameDetailAPIView(generics.RetrieveAPIView):
    queryset = Game.objects.all()
    serializer_class = GameSerializer
    lookup_field = "id"
    authentication_classes = [APITokenAuthentication]
    permission_classes = [IsAuthenticated]
