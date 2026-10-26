from django.urls import path

from .views import PartDetailView, PartListView, SuppliersWhoQuotedView

urlpatterns = [
    path("", PartListView.as_view(), name="part-list"),
    path("<int:pk>/", PartDetailView.as_view(), name="part-detail"),
    path("suppliers/who-quoted/", SuppliersWhoQuotedView.as_view(), name="suppliers-who-quoted"),
]
