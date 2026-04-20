from django.urls import path
from .views import (
    TeamContactListCreateView,
    TeamContactRetrieveUpdateDestroyView,
    TeamContactImportView,
    TeamContactMatchView,
    GmailCredentialView,
    GmailOAuthStartView,
    GmailOAuthCallbackView,
)

urlpatterns = [
    path("contacts/", TeamContactListCreateView.as_view(), name="team-contact-list-create"),
    path("contacts/<int:pk>/", TeamContactRetrieveUpdateDestroyView.as_view(), name="team-contact-detail"),
    path("contacts/import/", TeamContactImportView.as_view(), name="team-contact-import"),
    path("contacts/match/", TeamContactMatchView.as_view(), name="team-contact-match"),
    path("gmail/credential/", GmailCredentialView.as_view(), name="gmail-credential"),
    path("gmail/oauth/start/", GmailOAuthStartView.as_view(), name="gmail-oauth-start"),
    path("gmail/oauth/callback/", GmailOAuthCallbackView.as_view(), name="gmail-oauth-callback"),
]
