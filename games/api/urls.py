from django.urls import path
from .views import GameDetailAPIView

urlpatterns = [
    path('<uuid:id>/', GameDetailAPIView.as_view(), name='game-detail-api'),
]
