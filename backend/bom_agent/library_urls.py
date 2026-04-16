from django.urls import path
from .library_views import (
    LibraryDocumentListCreateView,
    LibraryDocumentDetailView,
    LibraryDocumentDownloadView,
    LibraryPromoteView,
)

urlpatterns = [
    path("documents/", LibraryDocumentListCreateView.as_view(), name="library-list-create"),
    path("documents/<int:pk>/", LibraryDocumentDetailView.as_view(), name="library-detail"),
    path("documents/<int:pk>/download/", LibraryDocumentDownloadView.as_view(), name="library-download"),
    path("documents/promote/", LibraryPromoteView.as_view(), name="library-promote"),
]
