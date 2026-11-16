import os
from urllib.parse import urlparse

from django.core.checks import Error, register


@register(deploy=True)
def gmail_oauth_deploy_check(app_configs, **kwargs):
    """Fail `manage.py check --deploy` when Gmail OAuth isn't production-ready."""
    errors = []
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    encryption_key = os.getenv("GMAIL_TOKEN_ENCRYPTION_KEY", "").strip()
    redirect_uri = os.getenv("GMAIL_OAUTH_REDIRECT_URI", "").strip()

    if not client_id.endswith(".apps.googleusercontent.com"):
        errors.append(
            Error(
                "GOOGLE_OAUTH_CLIENT_ID is missing or is not a Google OAuth client ID.",
                hint="Set it from Google Cloud Console → Google Auth Platform → Clients.",
                id="bom_agent.E001",
            )
        )
    if not client_secret:
        errors.append(
            Error("GOOGLE_OAUTH_CLIENT_SECRET is not set.", id="bom_agent.E002")
        )
    if not encryption_key:
        errors.append(
            Error(
                "GMAIL_TOKEN_ENCRYPTION_KEY is not set.",
                hint="Without it, stored Gmail tokens are keyed to SECRET_KEY and "
                "become unreadable if SECRET_KEY is rotated.",
                id="bom_agent.E003",
            )
        )
    if urlparse(redirect_uri).scheme != "https":
        errors.append(
            Error(
                "GMAIL_OAUTH_REDIRECT_URI must be set to an https:// URL.",
                hint="Use https://<backend-domain>/api/team/gmail/oauth/callback/ and "
                "register the same URI on the Google OAuth client.",
                id="bom_agent.E004",
            )
        )
    return errors
