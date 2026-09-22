from django.shortcuts import render

# Create your views here.
from django.contrib.auth import authenticate, login, logout
from ninja import Router

from StockPassCore.schemas.users import LoginSchema

router = Router()

from django.middleware.csrf import get_token

@router.get("/csrf")
def get_csrf_token(request):
    return {
        "csrfToken": get_token(request),
    }

@router.post("/login")
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

    login(request, user)

    return {
        "success": True,
        "message": "Login successful",
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
        },
    }

@router.post("/logout")
def logout_user(request):

    logout(request)

    return {
        "success": True,
        "message": "Logout successful",
    }

@router.get("/me")
def current_user(request):

    if not request.user.is_authenticated:
        return 401, {
            "success": False,
            "message": "Authentication required",
        }

    user = request.user

    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_active": user.is_active,
    }