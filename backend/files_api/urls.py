from django.urls import path
from .views import (
    AllFilesView,
    FileUploadView,
    FileExtractView,
    ProjectFileListView,
    FileDescriptionView,
    FileResultView,
    FileDeleteView,
    FileDownloadView,
    FileProfileDownloadView,
)

urlpatterns = [
    path("", AllFilesView.as_view(), name="all-files"),
    path("upload/", FileUploadView.as_view(), name="file-upload"),
    path(
        "project/<int:project_id>/", ProjectFileListView.as_view(), name="project-files"
    ),
    path(
        "<int:file_id>/description/",
        FileDescriptionView.as_view(),
        name="file-description",
    ),
    path("<int:file_id>/extract/", FileExtractView.as_view(), name="file-extract"),
    path("<int:file_id>/result/", FileResultView.as_view(), name="file-result"),
    path("<int:file_id>/", FileDeleteView.as_view(), name="file-delete"),
    path("<int:file_id>/download/", FileDownloadView.as_view(), name="file-download"),
    path("<int:file_id>/profile/", FileProfileDownloadView.as_view(), name="file-profile"),
]
