from django.urls import path
from .views import ChatView, SessionListView, SessionMessagesView, SessionStarView

urlpatterns = [
    path("chat/", ChatView.as_view(), name="assistant-chat"),
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
