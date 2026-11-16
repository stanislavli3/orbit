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
    ConnectorStatusView,
    ProjectSourcesView,
    SourceDetailView,
    SourceIndexView,
)

urlpatterns = [
    path("connectors/", ConnectorStatusView.as_view(), name="connector-status"),
    path("project/<int:project_id>/sources/", ProjectSourcesView.as_view(), name="project-sources"),
    path("sources/<int:source_id>/", SourceDetailView.as_view(), name="source-detail"),
    path("sources/<int:source_id>/index/", SourceIndexView.as_view(), name="source-index"),
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
