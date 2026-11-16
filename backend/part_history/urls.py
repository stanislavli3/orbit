from django.urls import path

from .sources_views import (
    SupplierSettingsDetailView,
    SupplierSettingsListView,
    WorkspaceSourceDetailView,
    WorkspaceSourceListView,
)

from .views import BomEstimateView, CostReductionView, EstimateStagesExportView, CostImportView, QuickEstimateView, PartDetailView, PartListView, SuppliersWhoQuotedView
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
    path("imports/", CostImportView.as_view(), name="cost-imports"),
    path("suppliers/who-quoted/", SuppliersWhoQuotedView.as_view(), name="suppliers-who-quoted"),
    path("sources/", WorkspaceSourceListView.as_view(), name="workspace-sources"),
    path("sources/<int:pk>/", WorkspaceSourceDetailView.as_view(), name="workspace-source-detail"),
    path("suppliers/", SupplierSettingsListView.as_view(), name="supplier-settings"),
    path("suppliers/<int:pk>/", SupplierSettingsDetailView.as_view(), name="supplier-settings-detail"),
    path("call-sheet/", CallSheetView.as_view(), name="call-sheet"),
    path("compare/", PartCompareView.as_view(), name="part-compare"),
    path("handoff/bom/<int:bom_id>/", HandoffTimelineView.as_view(), name="handoff-timeline"),
    path("handoff/summary/", HandoffSummaryView.as_view(), name="handoff-summary"),
]
