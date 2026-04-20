import csv
import io
from datetime import timedelta
from urllib.parse import urlencode, urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import TeamContact, GmailCredential
from .serializers import TeamContactSerializer, GmailCredentialSerializer
from .gmail_integration import (
    build_gmail_oauth_authorization_url,
    exchange_google_oauth_code,
    fetch_gmail_profile,
    google_oauth_is_configured,
    upsert_gmail_credential,
)


GMAIL_OAUTH_STATE_SALT = "bom-agent-gmail-oauth"


def _is_allowed_frontend_url(next_url: str) -> bool:
    if not next_url:
        return False
    parsed = urlparse(next_url)
    if not parsed.scheme and not parsed.netloc:
        return next_url.startswith("/")
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return origin in settings.CORS_ALLOWED_ORIGINS


def _default_settings_url() -> str:
    origin = (settings.CORS_ALLOWED_ORIGINS or ["http://localhost:5173"])[0]
    return f"{origin.rstrip('/')}/settings"


def _oauth_redirect_response(next_url: str, status_value: str, detail: str = ""):
    separator = "&" if "?" in next_url else "?"
    query = urlencode({"gmail_oauth": status_value, "detail": detail} if detail else {"gmail_oauth": status_value})
    return HttpResponseRedirect(f"{next_url}{separator}{query}")


class TeamContactListCreateView(generics.ListCreateAPIView):
    serializer_class = TeamContactSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = TeamContact.objects.filter(workspace_owner=self.request.user)
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(full_name__icontains=search) | qs.filter(
                role__icontains=search
            )
        tag = self.request.query_params.get("tag", "").strip()
        if tag:
            qs = qs.filter(expertise_tags__contains=tag)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            workspace_owner=self.request.user,
            added_by=self.request.user,
        )


class TeamContactRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TeamContactSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return TeamContact.objects.filter(workspace_owner=self.request.user)


class TeamContactImportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    # Expected CSV columns (case-insensitive)
    REQUIRED_COLS = {"name", "email", "role"}
    OPTIONAL_COLS = {"department", "tags"}

    def post(self, request):
        csv_file = request.FILES.get("file")
        if not csv_file:
            return Response(
                {"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST
            )

        dry_run = request.query_params.get("preview", "false").lower() == "true"

        try:
            text = csv_file.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            return Response(
                {"detail": "File must be UTF-8 encoded."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return Response(
                {"detail": "CSV file is empty."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Normalise header names
        col_map = {h.strip().lower(): h for h in reader.fieldnames}
        missing = self.REQUIRED_COLS - set(col_map.keys())
        if missing:
            return Response(
                {"detail": f"Missing required columns: {', '.join(sorted(missing))}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rows = []
        errors = []
        for i, row in enumerate(reader, start=2):  # row 1 = header
            name = row.get(col_map.get("name", ""), "").strip()
            email = row.get(col_map.get("email", ""), "").strip()
            role = row.get(col_map.get("role", ""), "").strip()
            department = row.get(col_map.get("department", ""), "").strip()
            tags_raw = row.get(col_map.get("tags", ""), "").strip()
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

            row_errors = []
            if not name:
                row_errors.append("Name is required")
            if not email:
                row_errors.append("Email is required")
            if not role:
                row_errors.append("Role is required")

            if row_errors:
                errors.append({"row": i, "errors": row_errors, "data": {"name": name, "email": email}})
            else:
                rows.append(
                    {
                        "full_name": name,
                        "email": email,
                        "role": role,
                        "department": department,
                        "expertise_tags": tags,
                    }
                )

        if dry_run:
            return Response(
                {
                    "preview": rows,
                    "errors": errors,
                    "valid_count": len(rows),
                    "error_count": len(errors),
                },
                status=status.HTTP_200_OK,
            )

        # Commit valid rows
        created = []
        skipped = []
        for entry in rows:
            obj, made = TeamContact.objects.get_or_create(
                workspace_owner=request.user,
                email=entry["email"],
                defaults={
                    **entry,
                    "added_by": request.user,
                },
            )
            if made:
                created.append(TeamContactSerializer(obj).data)
            else:
                skipped.append(entry["email"])

        return Response(
            {
                "created": created,
                "skipped": skipped,
                "errors": errors,
                "created_count": len(created),
                "skipped_count": len(skipped),
                "error_count": len(errors),
            },
            status=status.HTTP_201_CREATED,
        )


class TeamContactMatchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        question_type = request.query_params.get("question_type", "").strip().lower()
        if not question_type:
            return Response(
                {"detail": "question_type parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contacts = TeamContact.objects.filter(
            workspace_owner=request.user, allow_automated=True
        )

        # Exact tag match first, then partial name/role match
        exact = [c for c in contacts if question_type in [t.lower() for t in c.expertise_tags]]
        if exact:
            return Response(TeamContactSerializer(exact[0]).data)

        partial = [
            c
            for c in contacts
            if question_type in c.role.lower() or question_type in c.department.lower()
        ]
        if partial:
            return Response(TeamContactSerializer(partial[0]).data)

        return Response(
            {"detail": "No matching contact found."}, status=status.HTTP_404_NOT_FOUND
        )


class GmailCredentialView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        credential = GmailCredential.objects.filter(user=request.user).first()
        if credential is None:
            return Response({"connected": False, "credential": None})
        return Response(
            {
                "connected": True,
                "credential": GmailCredentialSerializer(credential).data,
            }
        )

    def patch(self, request):
        gmail_address = request.data.get("gmail_address", "").strip()
        access_token = request.data.get("access_token", "").strip()
        refresh_token = request.data.get("refresh_token", "").strip()
        token_expires_at_raw = request.data.get("token_expires_at")
        scopes_json = request.data.get("scopes_json") or []

        if not gmail_address:
            return Response(
                {"detail": "gmail_address is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not access_token and not refresh_token:
            return Response(
                {"detail": "Provide an access_token or refresh_token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(scopes_json, list):
            return Response(
                {"detail": "scopes_json must be a list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token_expires_at = parse_datetime(token_expires_at_raw) if token_expires_at_raw else None
        credential = upsert_gmail_credential(
            user=request.user,
            gmail_address=gmail_address,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            scopes_json=scopes_json,
        )
        return Response(GmailCredentialSerializer(credential).data)

    def delete(self, request):
        GmailCredential.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GmailOAuthStartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not google_oauth_is_configured():
            return Response(
                {"detail": "Google OAuth client credentials are not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        next_url = request.data.get("next_url", "").strip() or _default_settings_url()
        if not _is_allowed_frontend_url(next_url):
            return Response(
                {"detail": "next_url must be a permitted frontend URL."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        state = signing.dumps(
            {"user_id": request.user.id, "next_url": next_url},
            salt=GMAIL_OAUTH_STATE_SALT,
        )
        try:
            auth_url = build_gmail_oauth_authorization_url(request, state)
        except RuntimeError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"auth_url": auth_url})


class GmailOAuthCallbackView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        raw_state = request.query_params.get("state", "")
        next_url = _default_settings_url()

        if not raw_state:
            return _oauth_redirect_response(next_url, "error", "Missing OAuth state.")

        try:
            state = signing.loads(raw_state, salt=GMAIL_OAUTH_STATE_SALT, max_age=600)
        except signing.BadSignature:
            return _oauth_redirect_response(next_url, "error", "OAuth state is invalid or expired.")

        signed_next_url = state.get("next_url", "").strip()
        if _is_allowed_frontend_url(signed_next_url):
            next_url = signed_next_url

        if request.query_params.get("error"):
            return _oauth_redirect_response(
                next_url,
                "error",
                request.query_params.get("error_description", "Gmail access was not granted."),
            )

        code = request.query_params.get("code", "").strip()
        if not code:
            return _oauth_redirect_response(next_url, "error", "Missing authorization code.")

        try:
            token_payload = exchange_google_oauth_code(request, code)
            access_token = token_payload.get("access_token", "")
            refresh_token = token_payload.get("refresh_token", "")
            expires_in = int(token_payload.get("expires_in", 3600))
            if not access_token:
                raise RuntimeError("Google token exchange did not return an access token.")

            profile = fetch_gmail_profile(access_token)
            gmail_address = profile.get("emailAddress", "").strip()
            if not gmail_address:
                raise RuntimeError("Google profile did not include an email address.")

            user_id = state.get("user_id")
            user = get_user_model().objects.get(id=user_id)
            upsert_gmail_credential(
                user=user,
                gmail_address=gmail_address,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=timezone.now() + timedelta(seconds=expires_in),
                scopes_json=(token_payload.get("scope", "") or "").split(),
            )
        except Exception as exc:
            return _oauth_redirect_response(next_url, "error", str(exc))

        return _oauth_redirect_response(next_url, "connected")
