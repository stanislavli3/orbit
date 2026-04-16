from django.contrib import admin
from .models import TeamContact


@admin.register(TeamContact)
class TeamContactAdmin(admin.ModelAdmin):
    list_display = ["full_name", "email", "role", "department", "workspace_owner", "allow_automated"]
    list_filter = ["preferred_channel", "allow_automated"]
    search_fields = ["full_name", "email", "role"]
