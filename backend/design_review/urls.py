from django.urls import path

from . import views

urlpatterns = [
    path("<int:pk>/members/", views.MemberListCreateView.as_view(), name="review-members"),
    path("<int:pk>/members/<int:member_id>/", views.MemberDeleteView.as_view(), name="review-member-delete"),
    path("<int:pk>/changes/", views.ChangeListCreateView.as_view(), name="review-changes"),
    path("<int:pk>/changes/<int:change_id>/", views.ChangeDetailView.as_view(), name="review-change-detail"),
    path("<int:pk>/changes/<int:change_id>/decision/", views.ChangeDecisionView.as_view(), name="review-change-decision"),
    path(
        "<int:pk>/changes/<int:change_id>/interference/",
        views.InterferenceCheckView.as_view(),
        name="review-change-interference",
    ),
]
