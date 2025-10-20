# accounts/auth_backends.py

import bcrypt
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.hashers import check_password as django_check_password

from .models import User


class LegacyBackend(ModelBackend):
    """
    Primero prueba con el sistema de hash de Django.
    Si falla, prueba directamente bcrypt contra tu hash legado.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return None

        # 1) Django check (PBKDF2, bcrypt_sha256, etc)
        if django_check_password(password, user.password):
            return user

        # 2) Fallback a bcrypt puro
        stored = user.password
        # aseguramos bytes
        stored_bytes = stored.encode("utf-8") if isinstance(stored, str) else stored
        if bcrypt.checkpw(password.encode("utf-8"), stored_bytes):
            return user

        return None
