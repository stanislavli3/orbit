import os
import jwt
from django.contrib.auth.models import User

CLERK_JWT_KEY = os.getenv("CLERK_JWT_KEY")

def verify_clerk_token(token: str):
    if not CLERK_JWT_KEY:
        raise Exception("Missing CLERK_JWT_KEY")

    payload = jwt.decode(
        token,
        CLERK_JWT_KEY,
        algorithms=["RS256"],
        options={"verify_aud": False},
    )
    return payload

def get_or_create_local_user_from_clerk_payload(payload):
    clerk_user_id = payload.get("sub")
    if not clerk_user_id:
        raise Exception("Token missing sub claim")

    username = f"clerk_{clerk_user_id}"

    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "email": payload.get("email", ""),
            "first_name": payload.get("given_name", ""),
            "last_name": payload.get("family_name", ""),
        },
    )

    return user