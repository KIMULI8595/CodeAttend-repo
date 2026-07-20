from django.contrib.auth import authenticate

from core.exceptions import AccountNotActiveError
from accounts.models import AccountStatus


class AuthenticationService:

    @staticmethod
    def login(email, password):

        user = authenticate(
            email=email,
            password=password
        )

        if not user:
            return None

        if (
            user.account_status != AccountStatus.ACTIVE
            and not user.is_superuser
        ):   
            raise AccountNotActiveError(
                "Your account is not active yet."
        )


        return user