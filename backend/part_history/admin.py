from django.contrib import admin

from .models import HistoricalCost, Part, Quote, Supplier


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ["part_number", "description", "material", "process", "workspace_owner"]
    search_fields = ["part_number", "description", "material"]


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ["name", "is_approved", "certifications", "workspace_owner"]
    list_filter = ["is_approved"]
    search_fields = ["name", "certifications"]


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ["supplier", "part", "material", "tolerance", "unit_price", "lead_time_days", "quoted_at", "source"]
    list_filter = ["quoted_at"]
    search_fields = ["supplier__name", "part__part_number", "material", "tolerance", "certifications"]


@admin.register(HistoricalCost)
class HistoricalCostAdmin(admin.ModelAdmin):
    list_display = ["part", "unit_cost", "program", "model_year", "source", "is_sample"]
    list_filter = ["is_sample", "model_year"]
    search_fields = ["part__part_number", "program", "source"]
