# StockPassCore/schemas/users.py

from ninja import Schema
from typing import Optional
from StockPassCore.models.users import User

class UserCreateSchema(Schema):
    username: str
    password: str
    role: User.Role = User.Role.LABOUR

    first_name: str = ""
    last_name: str = ""
    email: Optional[str] = None
    phone_number: Optional[str] = None
    gender_code: Optional[str] = None
    profile_picture: Optional[str] = None


class UserUpdateSchema(Schema):
    role: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    gender_code: Optional[str] = None
    profile_picture: Optional[str] = None


class UserOutSchema(Schema):
    id: int
    username: str
    role: str
    first_name: str
    last_name: str
    email: str
    phone_number: Optional[str]
    gender_code: Optional[str]
    profile_picture: Optional[str]
    is_active: bool


class LoginSchema(Schema):
    username: str
    password: str


class ChangePasswordSchema(Schema):
    new_password: str