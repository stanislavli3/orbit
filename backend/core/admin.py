from django.contrib import admin
from django.utils import timezone

from .models import JobFailure


@admin.register(JobFailure)
class JobFailureAdmin(admin.ModelAdmin):
    list_display = [
        "last_seen_at",
        "job_type",
        "target_id",
        "error_class",
        "occurrences",
        "resolved_at",
    ]
    list_filter = ["job_type", "resolved_at"]
    search_fields = ["job_type", "target_id", "error_class", "error_message"]
    date_hierarchy = "last_seen_at"
    actions = ["mark_resolved"]

    def has_add_permission(self, request):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields if f.name != "resolved_at"]

    @admin.action(description="Mark selected failures resolved")
    def mark_resolved(self, request, queryset):
        queryset.filter(resolved_at__isnull=True).update(resolved_at=timezone.now())
