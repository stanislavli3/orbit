from django.contrib import admin

from .models import Change, ChangeEvent, InterferenceCheck, ProjectMember

admin.site.register(ProjectMember)
admin.site.register(Change)
admin.site.register(InterferenceCheck)


@admin.register(ChangeEvent)
class ChangeEventAdmin(admin.ModelAdmin):
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
