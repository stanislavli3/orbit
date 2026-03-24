from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .clerk_auth import verify_clerk_token, get_or_create_local_user_from_clerk_payload

class ClerkAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return None

        if not auth_header.startswith("Bearer "):
            raise AuthenticationFailed("Invalid authorization header")

        token = auth_header.split(" ", 1)[1].strip()

        try:
            payload = verify_clerk_token(token)
            user = get_or_create_local_user_from_clerk_payload(payload)
            return (user, payload)
        except Exception as e:
            raise AuthenticationFailed(f"Invalid Clerk token: {str(e)}")