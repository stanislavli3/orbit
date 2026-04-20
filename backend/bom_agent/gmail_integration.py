import base64
import hashlib
import json
import os
from datetime import timedelta
from email.message import EmailMessage
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .models import GmailCredential, TeamRequest
from .team_requests import apply_parsed_answer, maybe_resume_research, parse_reply_answer


GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_OAUTH_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def _fernet() -> Fernet:
    raw_key = os.getenv("GMAIL_TOKEN_ENCRYPTION_KEY", settings.SECRET_KEY).encode()
    digest = hashlib.sha256(raw_key).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    return _fernet().decrypt(value.encode()).decode()


def upsert_gmail_credential(
    *,
    user,
    gmail_address: str,
    access_token: str = "",
    refresh_token: str = "",
    token_expires_at=None,
    scopes_json: list[str] | None = None,
):
    defaults = {
        "gmail_address": gmail_address,
        "scopes_json": scopes_json or [],
    }
    if access_token:
        defaults["encrypted_access_token"] = encrypt_secret(access_token)
    if refresh_token:
        defaults["encrypted_refresh_token"] = encrypt_secret(refresh_token)
    if token_expires_at is not None:
        defaults["token_expires_at"] = token_expires_at
    return GmailCredential.objects.update_or_create(user=user, defaults=defaults)[0]


def google_oauth_is_configured() -> bool:
    return bool(
        os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
        and os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    )


def gmail_oauth_redirect_uri(request) -> str:
    return request.build_absolute_uri(reverse("gmail-oauth-callback"))


def build_gmail_oauth_authorization_url(request, state: str) -> str:
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    if not client_id:
        raise RuntimeError("Google OAuth client credentials are not configured.")

    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": gmail_oauth_redirect_uri(request),
            "response_type": "code",
            "scope": " ".join(GMAIL_OAUTH_SCOPES),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
        }
    )
    return f"{GOOGLE_OAUTH_AUTH_URL}?{query}"


def _gmail_request(method: str, path: str, access_token: str, payload: dict | None = None):
    data = None
    headers = {"Authorization": f"Bearer {access_token}"}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"

    request = Request(
        f"{GMAIL_API_BASE}/{path.lstrip('/')}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=20) as response:
            body = response.read().decode()
            return json.loads(body) if body else {}
    except HTTPError as exc:
        detail = exc.read().decode()
        raise RuntimeError(f"Gmail API error ({exc.code}): {detail or exc.reason}") from exc


def _refresh_access_token(credential: GmailCredential) -> str:
    refresh_token = decrypt_secret(credential.encrypted_refresh_token)
    if not refresh_token:
        raise RuntimeError("No Gmail refresh token is stored for this user.")

    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Google OAuth client credentials are not configured.")

    payload = json.dumps(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode()
    request = Request(
        GMAIL_TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode())
    except HTTPError as exc:
        detail = exc.read().decode()
        raise RuntimeError(f"Google token refresh failed ({exc.code}): {detail or exc.reason}") from exc

    access_token = body.get("access_token", "")
    if not access_token:
        raise RuntimeError("Google token refresh did not return an access token.")

    credential.encrypted_access_token = encrypt_secret(access_token)
    expires_in = int(body.get("expires_in", 3600))
    credential.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
    credential.save(update_fields=["encrypted_access_token", "token_expires_at", "updated_at"])
    return access_token


def exchange_google_oauth_code(request, code: str) -> dict:
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Google OAuth client credentials are not configured.")

    payload = urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": gmail_oauth_redirect_uri(request),
        }
    ).encode()
    oauth_request = Request(
        GMAIL_TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(oauth_request, timeout=20) as response:
            return json.loads(response.read().decode())
    except HTTPError as exc:
        detail = exc.read().decode()
        raise RuntimeError(
            f"Google token exchange failed ({exc.code}): {detail or exc.reason}"
        ) from exc


def fetch_gmail_profile(access_token: str) -> dict:
    return _gmail_request("GET", "/profile", access_token)


def get_valid_access_token(user) -> tuple[GmailCredential, str]:
    credential = GmailCredential.objects.filter(user=user).first()
    if credential is None:
        raise RuntimeError("No Gmail credential is connected for this user.")

    if credential.encrypted_access_token and credential.token_expires_at and credential.token_expires_at > timezone.now() + timedelta(minutes=5):
        return credential, decrypt_secret(credential.encrypted_access_token)

    if credential.encrypted_refresh_token:
        return credential, _refresh_access_token(credential)

    if credential.encrypted_access_token:
        return credential, decrypt_secret(credential.encrypted_access_token)

    raise RuntimeError("No usable Gmail access token is available for this user.")


def send_team_request_via_gmail(team_request: TeamRequest) -> dict:
    credential, access_token = get_valid_access_token(team_request.run.created_by)

    message = EmailMessage()
    message["To"] = team_request.recipient_email
    message["From"] = credential.gmail_address
    message["Subject"] = team_request.email_subject
    message.set_content(team_request.email_body)

    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    payload = {"raw": encoded_message}
    if team_request.gmail_thread_id:
        payload["threadId"] = team_request.gmail_thread_id
    payload = _gmail_request("POST", "/messages/send", access_token, payload)
    return {
        "gmail_address": credential.gmail_address,
        "message_id": payload.get("id", ""),
        "thread_id": payload.get("threadId", ""),
    }


def _payload_headers(message: dict) -> dict[str, str]:
    headers = {}
    for header in message.get("payload", {}).get("headers", []):
        name = header.get("name")
        if name:
            headers[name.lower()] = header.get("value", "")
    return headers


def _extract_plain_text(payload: dict) -> str:
    mime_type = payload.get("mimeType")
    body_data = payload.get("body", {}).get("data")
    if mime_type == "text/plain" and body_data:
        return base64.urlsafe_b64decode(body_data + "=" * (-len(body_data) % 4)).decode(errors="ignore")
    for part in payload.get("parts", []) or []:
        text = _extract_plain_text(part)
        if text:
            return text
    if body_data:
        return base64.urlsafe_b64decode(body_data + "=" * (-len(body_data) % 4)).decode(errors="ignore")
    return ""


def _latest_inbound_message(team_request: TeamRequest, gmail_address: str, access_token: str) -> dict | None:
    if not team_request.gmail_thread_id:
        return None
    thread = _gmail_request("GET", f"/threads/{team_request.gmail_thread_id}", access_token)
    messages = thread.get("messages", []) or []
    for message in reversed(messages):
        if message.get("id") in {team_request.gmail_message_id, team_request.gmail_reply_message_id}:
            continue
        headers = _payload_headers(message)
        sender = headers.get("from", "").lower()
        if team_request.recipient_email.lower() not in sender:
            continue
        if gmail_address.lower() in sender:
            continue
        return message
    return None


def sync_team_request_reply(team_request: TeamRequest) -> bool:
    if team_request.status not in {"sent", "follow_up"}:
        return False

    credential, access_token = get_valid_access_token(team_request.run.created_by)
    message = _latest_inbound_message(team_request, credential.gmail_address, access_token)
    team_request.last_checked_at = timezone.now()
    if not message:
        team_request.save(update_fields=["last_checked_at"])
        return False

    reply_text = _extract_plain_text(message.get("payload", {})).strip() or message.get("snippet", "").strip()
    parsed = parse_reply_answer(team_request, reply_text)
    apply_parsed_answer(team_request, parsed)

    team_request.status = "answered"
    team_request.answered_at = timezone.now()
    team_request.response = reply_text
    team_request.gmail_reply_message_id = message.get("id", "")
    team_request.last_checked_at = timezone.now()
    team_request.save(
        update_fields=[
            "status",
            "answered_at",
            "response",
            "gmail_reply_message_id",
            "last_checked_at",
        ]
    )

    line_item_name = team_request.line_item.part_name if team_request.line_item else team_request.question_key or "BOM item"
    resume_message = f"{team_request.recipient_name} confirmed {parsed.get('value')} for {line_item_name} — research resumed"
    maybe_resume_research(team_request.run, resume_message)
    return True


def poll_run_replies(run) -> list[int]:
    answered_ids: list[int] = []
    for team_request in run.team_requests.filter(status__in=["sent", "follow_up"]).order_by("created_at"):
        if sync_team_request_reply(team_request):
            answered_ids.append(team_request.id)
    return answered_ids
