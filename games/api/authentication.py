from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings
from django.contrib.auth.models import User


class APITokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        token = self._get_token_from_request(request)

        if not token:
            return None

        self._validate_token(token)
        # Return the first active staff user
        user = User.objects.filter(is_active=True, is_staff=True).first()
        return (user, token)

    def _get_token_from_request(self, request):
        # Try URL parameter first (for DRF browsable API)
        token = request.GET.get("api_token")
        if token:
            return token

        # Fall back to Authorization header
        return self._get_token_from_header(request)

    def _get_token_from_header(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION")
        if not auth_header:
            return None

        token_parts = auth_header.split(" ", 1)
        if len(token_parts) != 2:
            raise AuthenticationFailed("Invalid token format")

        token_type, token = token_parts
        if token_type.lower() != "bearer":
            raise AuthenticationFailed("Invalid token type")

        return token

    def _validate_token(self, token):
        expected_token = getattr(settings, "API_TOKEN", None)
        if not expected_token:
            raise AuthenticationFailed("API token not configured")

        if token != expected_token:
            raise AuthenticationFailed("Invalid token")
