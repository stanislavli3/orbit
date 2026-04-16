from django.urls import path
from .bom_views import (
    BomRunListCreateView,
    BomRunDetailView,
    BomRunInputsView,
    BomRunQuestionsView,
    BomRunExcelView,
)

urlpatterns = [
    path("runs/", BomRunListCreateView.as_view(), name="bom-run-list-create"),
    path("runs/<int:pk>/", BomRunDetailView.as_view(), name="bom-run-detail"),
    path("runs/<int:pk>/inputs/", BomRunInputsView.as_view(), name="bom-run-inputs"),
    path("runs/<int:pk>/questions/", BomRunQuestionsView.as_view(), name="bom-run-questions"),
    path("runs/<int:pk>/excel/", BomRunExcelView.as_view(), name="bom-run-excel"),
]
