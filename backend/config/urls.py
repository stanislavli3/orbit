from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    path("api/projects/", include("projects.urls")),
    path("api/files/", include("files_api.urls")),
    path("api/auth/", include("accounts.urls")),
]
