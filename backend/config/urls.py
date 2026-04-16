from django.contrib import admin
from django.urls import path, include
from projects.views import HistoryView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    path("api/projects/", include("projects.urls")),
    path("api/files/", include("files_api.urls")),
    path("api/assistant/", include("assistant.urls")),
    path("api/auth/", include("accounts.urls")),
    path("api/history/", HistoryView.as_view(), name="history"),
    path("api/team/", include("bom_agent.urls")),
    path("api/bom/", include("bom_agent.bom_urls")),
    path("api/library/", include("bom_agent.library_urls")),
]
