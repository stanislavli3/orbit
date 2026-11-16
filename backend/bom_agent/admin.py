from django.contrib import admin
from .models import Bom, BomRow, TeamContact


@admin.register(TeamContact)
class TeamContactAdmin(admin.ModelAdmin):
    list_display = ["full_name", "email", "role", "department", "workspace_owner", "allow_automated"]
    list_filter = ["preferred_channel", "allow_automated"]
    search_fields = ["full_name", "email", "role"]


class BomRowInline(admin.TabularInline):
    model = BomRow
    extra = 0
    fields = ["line_no", "part_number", "description", "material", "process", "quantity", "spec", "confidence", "edited"]


@admin.register(Bom)
class BomAdmin(admin.ModelAdmin):
    list_display = ["id", "source_name", "project", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["source_name", "rows__part_number"]
    inlines = [BomRowInline]
