from django.urls import path

from .views import SpendImportView, SupplierResearchView
from .views import (
    BomEstimateView, CallSheetView, HandoffSummaryView, HandoffTimelineView, PartCompareView,
)
from .views import CostReductionView, EstimateStagesExportView, CostImportView, QuickEstimateView, PartDetailView, PartListView, SuppliersWhoQuotedView

urlpatterns = [
    path("", PartListView.as_view(), name="part-list"),
    path("<int:pk>/", PartDetailView.as_view(), name="part-detail"),
    path("estimate/bom/<int:bom_id>/", BomEstimateView.as_view(), name="bom-estimate"),
    path("estimate/bom/<int:bom_id>/stages.xlsx", EstimateStagesExportView.as_view(), name="bom-estimate-stages"),
    path("quick-estimate/", QuickEstimateView.as_view(), name="quick-estimate"),
    path("quick-estimate/<int:bom_id>/", QuickEstimateView.as_view(), name="quick-estimate-report"),
    path("cost-reduction/<int:row_id>/", CostReductionView.as_view(), name="cost-reduction"),
    path("spend-imports/", SpendImportView.as_view(), name="spend-imports"),
    path("supplier-research/<int:row_id>/", SupplierResearchView.as_view(), name="supplier-research"),
    path("imports/", CostImportView.as_view(), name="cost-imports"),
    path("suppliers/who-quoted/", SuppliersWhoQuotedView.as_view(), name="suppliers-who-quoted"),
    path("call-sheet/", CallSheetView.as_view(), name="call-sheet"),
    path("compare/", PartCompareView.as_view(), name="part-compare"),
    path("handoff/bom/<int:bom_id>/", HandoffTimelineView.as_view(), name="handoff-timeline"),
    path("handoff/summary/", HandoffSummaryView.as_view(), name="handoff-summary"),
]
