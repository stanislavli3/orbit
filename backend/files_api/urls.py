from django.urls import path
from .views import FileUploadView, ProjectFileListView

urlpatterns = [
    path("upload/", FileUploadView.as_view(), name="file-upload"),
    path(
        "project/<int:project_id>/", ProjectFileListView.as_view(), name="project-files"
    ),
]
