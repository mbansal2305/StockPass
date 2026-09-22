from ninja.security import SessionAuth


class OwnerAdminAuth(SessionAuth):

    def authenticate(self, request, key=None):
        user = request.user

        if not user.is_authenticated:
            return None

        if user.role not in [
            user.Role.OWNER,
            user.Role.ADMIN,
        ]:
            return None

        return user