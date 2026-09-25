from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone

from ninja import Router

from StockPassCore.auth.permissions import OwnerAdminAuth
from StockPassCore.schemas.users import (
    UserCreateSchema,
    UserUpdateSchema,
    UserOutSchema,
    ChangePasswordSchema,
)

User = get_user_model()

router = Router(
    auth=OwnerAdminAuth()
)



# LIST USERS
@router.get("/", response=list[UserOutSchema])
def list_users(request):
    """
    Get all users.

    Only OWNER and ADMIN can access this endpoint.
    """

    users = User.objects.all().order_by("username")

    return users

# GET USER
@router.get("/{user_id}", response=UserOutSchema)
def get_user(request, user_id: int):
    """
    Get a single user by ID.
    """

    user = get_object_or_404(User, id=user_id)

    return user

# CREATE USER
@router.post("/", response=UserOutSchema)
def create_user(request, data: UserCreateSchema):
    """
    Create a new user.

    Only OWNER and ADMIN can create users.
    """

    # --------------------------------------------------------
    # Check username
    # --------------------------------------------------------

    if User.objects.filter(username=data.username).exists():
        return 400, {
            "success": False,
            "message": "Username already exists.",
        }

    # --------------------------------------------------------
    # Create user
    # --------------------------------------------------------

    user = User.objects.create_user(
        username=data.username,
        password=data.password,
        role=data.role,
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
        phone_number=data.phone_number,
        gender_code=data.gender_code,
        profile_picture=data.profile_picture,
        is_active=True,
    )

    return user


# UPDATE USER
@router.patch("/{user_id}", response=UserOutSchema)
def update_user(
    request,
    user_id: int,
    data: UserUpdateSchema,
):
    """
    Update user information.

    Password is NOT changed through this endpoint.
    Use the password endpoint for that.
    """

    user = get_object_or_404(User, id=user_id)

    # --------------------------------------------------------
    # Update only fields supplied in request
    # --------------------------------------------------------

    update_fields = []

    if data.role is not None:
        user.role = data.role
        update_fields.append("role")

    if data.first_name is not None:
        user.first_name = data.first_name
        update_fields.append("first_name")

    if data.last_name is not None:
        user.last_name = data.last_name
        update_fields.append("last_name")

    if data.email is not None:
        user.email = data.email
        update_fields.append("email")

    if data.phone_number is not None:
        user.phone_number = data.phone_number
        update_fields.append("phone_number")

    if data.gender_code is not None:
        user.gender_code = data.gender_code
        update_fields.append("gender_code")

    if data.profile_picture is not None:
        user.profile_picture = data.profile_picture
        update_fields.append("profile_picture")

    if update_fields:
        user.save(update_fields=update_fields)

    return user


# TOGGLE USER STATUS
@router.patch("/{user_id}/toggle")
def toggle_user_status(request, user_id: int):
    """
    Toggle a user's active status.

    A disabled user cannot log in. Users cannot disable their own account.
    """

    user = get_object_or_404(User, id=user_id)

    # --------------------------------------------------------
    # Prevent disabling yourself
    # --------------------------------------------------------

    if user.id == request.user.id and user.is_active:
        return 400, {
            "success": False,
            "message": "You cannot disable your own account.",
        }

    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])

    return {
        "success": True,
        "message": f"User {'enabled' if user.is_active else 'disabled'} successfully.",
    }


# CHANGE USER PASSWORD
@router.patch("/{user_id}/password")
def change_user_password(
    request,
    user_id: int,
    data: ChangePasswordSchema,
):
    """
    Change another user's password.

    Only OWNER and ADMIN can perform this operation.
    """

    user = get_object_or_404(User, id=user_id)

    # --------------------------------------------------------
    # Set password using Django's password hashing mechanism
    # --------------------------------------------------------

    user.set_password(data.new_password)

    user.save(update_fields=["password"])

    return {
        "success": True,
        "message": "Password changed successfully.",
    }


# DELETE USER
@router.delete("/{user_id}")
def delete_user(request, user_id: int):
    """
    Soft-delete a user.

    The user is disabled rather than physically deleted.
    """

    user = get_object_or_404(User, id=user_id)

    # --------------------------------------------------------
    # Prevent deleting yourself
    # --------------------------------------------------------

    if user.id == request.user.id:
        return 400, {
            "success": False,
            "message": "You cannot delete your own account.",
        }

    # --------------------------------------------------------
    # Soft delete
    # --------------------------------------------------------

    user.is_active = False

    user.save(update_fields=["is_active"])

    return {
        "success": True,
        "message": "User deleted successfully.",
    }