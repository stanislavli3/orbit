from django.urls import path
from .views import (
    FileUploadView,
    ProjectFileListView,
    FileDescriptionView,
    FileResultView,
)

urlpatterns = [
    path("upload/", FileUploadView.as_view(), name="file-upload"),
    path(
        "project/<int:project_id>/", ProjectFileListView.as_view(), name="project-files"
    ),
    path(
        "<int:file_id>/description/",
        FileDescriptionView.as_view(),
        name="file-description",
    ),
    path("<int:file_id>/result/", FileResultView.as_view(), name="file-result"),
]
