from ninja.security import HttpBearer
from rest_framework_simplejwt.authentication import JWTAuthentication


class JWTAuth(HttpBearer):

    def authenticate(self, request, token):

        jwt_auth = JWTAuthentication()

        try:
            validated_token = jwt_auth.get_validated_token(token)
            user = jwt_auth.get_user(validated_token)

        except Exception:
            return None

        if not user.is_active:
            return None

        return user


class OwnerAdminAuth(HttpBearer):

    def authenticate(self, request, token):

        jwt_auth = JWTAuthentication()

        try:
            validated_token = jwt_auth.get_validated_token(token)
            user = jwt_auth.get_user(validated_token)

        except Exception:
            return None

        if not user.is_active:
            return None

        if user.role not in [
            user.Role.OWNER,
            user.Role.ADMIN,
        ]:
            return None

        return user