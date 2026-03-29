from django.urls import path
from .views import ProjectListCreateView, ProjectRetrieveView, ProjectExportView

urlpatterns = [
    path("", ProjectListCreateView.as_view(), name="project-list-create"),
    path("<int:pk>/", ProjectRetrieveView.as_view(), name="project-detail"),
    path("<int:pk>/export/", ProjectExportView.as_view(), name="project-export"),
]
