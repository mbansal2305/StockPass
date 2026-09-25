from django.contrib.auth import authenticate
from ninja import Router

from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from StockPassCore.auth.permissions import JWTAuth
from StockPassCore.schemas.users import (
    LoginSchema,
    LogoutSchema,
    RefreshTokenSchema,
)


router = Router()


# ============================================================
# LOGIN
# ============================================================

@router.post(
    "/login/",
    response={200: dict, 401: dict, 403: dict},
)
def login_user(request, data: LoginSchema):

    user = authenticate(
        request,
        username=data.username,
        password=data.password,
    )

    if user is None:
        return 401, {
            "success": False,
            "message": "Invalid username or password",
        }

    if not user.is_active:
        return 403, {
            "success": False,
            "message": "User account is disabled",
        }

    refresh = RefreshToken.for_user(user)

    return {
        "success": True,
        "message": "Login successful",
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
        "token_type": "Bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_active": user.is_active,
        },
    }


# ============================================================
# ME
# ============================================================

@router.get("/me/", auth=JWTAuth())
def current_user(request):

    user = request.auth

    return {
        "success": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "phone_number": user.phone_number,
            "gender_code": user.gender_code,
            "profile_picture": user.profile_picture,
            "is_active": user.is_active,
        },
    }


# ============================================================
# REFRESH TOKEN
# ============================================================

@router.post("/refresh/")
def refresh_token(request, data: RefreshTokenSchema):

    try:
        old_refresh = RefreshToken(data.refresh_token)

        user_id = old_refresh["user_id"]

        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.get(id=user_id)

        if not user.is_active:
            return 403, {
                "success": False,
                "message": "User account is disabled",
            }

        # Blacklist old refresh token
        old_refresh.blacklist()

        # Create new tokens
        new_refresh = RefreshToken.for_user(user)

        return {
            "success": True,
            "access_token": str(new_refresh.access_token),
            "refresh_token": str(new_refresh),
            "token_type": "Bearer",
        }

    except TokenError:
        return 401, {
            "success": False,
            "message": "Invalid or expired refresh token",
        }

    except User.DoesNotExist:
        return 401, {
            "success": False,
            "message": "User does not exist",
        }

# ============================================================
# LOGOUT
# ============================================================

@router.post("/logout/", auth=JWTAuth())
def logout_user(request, data: LogoutSchema):

    try:
        refresh = RefreshToken(data.refresh_token)
        refresh.blacklist()

        return {
            "success": True,
            "message": "Logout successful",
        }

    except TokenError:
        return 401, {
            "success": False,
            "message": "Invalid or expired refresh token",
        }