from django.test import TestCase

from StockPassCore.models import User


class UserManagerTests(TestCase):
    def test_create_superuser_defaults_to_owner_role(self):
        user = User.objects.create_superuser(
            username="owner",
            email="owner@example.com",
            password="test-password",
        )

        self.assertEqual(user.role, User.Role.OWNER)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_create_user_keeps_labour_role_default(self):
        user = User.objects.create_user(
            username="labour",
            email="labour@example.com",
            password="test-password",
        )

        self.assertEqual(user.role, User.Role.LABOUR)
