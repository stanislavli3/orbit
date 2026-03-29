from django.urls import path
from .views import ProjectListCreateView, ProjectRetrieveUpdateDestroyView, ProjectExportView

urlpatterns = [
    path("", ProjectListCreateView.as_view(), name="project-list-create"),
    path(
        "<int:pk>/", ProjectRetrieveUpdateDestroyView.as_view(), name="project-detail"
    ),
    path("<int:pk>/export/", ProjectExportView.as_view(), name="project-export"),
]
