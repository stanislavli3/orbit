from django.urls import path
from .views import (
    AskInContextView,
    ChatView,
    SessionListView,
    SessionMessagesView,
    SessionStarView,
    UnifiedSearchView,
)

urlpatterns = [
    path("chat/", ChatView.as_view(), name="assistant-chat"),
    path("search/", UnifiedSearchView.as_view(), name="assistant-search"),
    path("ask/", AskInContextView.as_view(), name="assistant-ask"),
    path("sessions/", SessionListView.as_view(), name="assistant-sessions"),
    path(
        "sessions/<uuid:session_id>/messages/",
        SessionMessagesView.as_view(),
        name="assistant-session-messages",
    ),
    path(
        "sessions/<uuid:session_id>/star/",
        SessionStarView.as_view(),
        name="assistant-session-star",
    ),
]
