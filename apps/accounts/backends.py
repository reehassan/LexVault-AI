# apps/accounts/backends.py
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend

User = get_user_model()


class FirmBackend(BaseBackend):
    """
    Authenticates users scoped to a Firm: (firm, username, password).

    Requires `firm` to be passed explicitly in the authenticate() call,
    e.g. authenticate(request, firm=firm_instance, username=..., password=...)
    """

    def authenticate(self, request, firm=None, username=None, password=None, **kwargs):
        if firm is None or username is None or password is None:
            return None

        try:
            user = User.objects.get(firm=firm, username=username)
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            # Should never happen if the (firm, username) constraint holds —
            # but fail closed rather than guessing which user was meant.
            return None

        if user.check_password(password):
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None