from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from ninja.security import HttpBearer
from ninja_jwt.exceptions import TokenError
from ninja_jwt.tokens import AccessToken


class LiveUserJWTAuth(HttpBearer):
    def authenticate(self, request, token):
        try:
            validated = AccessToken(token)
            return get_user_model().objects.get(pk=validated["user_id"], is_active=True)
        except (TokenError, ObjectDoesNotExist, KeyError):
            return None
