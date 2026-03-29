from django.urls import path
from .views import ProjectListCreateView, ProjectRetrieveUpdateDestroyView

urlpatterns = [
    path("", ProjectListCreateView.as_view(), name="project-list-create"),
    path(
        "<int:pk>/", ProjectRetrieveUpdateDestroyView.as_view(), name="project-detail"
    ),
]
