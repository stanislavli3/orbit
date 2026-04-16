from rest_framework import serializers
from .models import TeamContact, BomResearchRun, BomLineItem, SupplierQuote, LibraryDocument


class LibraryDocumentSerializer(serializers.ModelSerializer):
    bom_run_count = serializers.SerializerMethodField()

    class Meta:
        model = LibraryDocument
        fields = [
            "id",
            "original_name",
            "doc_type",
            "file_type",
            "file_size",
            "uploaded_at",
            "bom_run_count",
        ]
        read_only_fields = ["id", "original_name", "file_type", "file_size", "uploaded_at", "bom_run_count"]

    def get_bom_run_count(self, obj):
        return obj.bom_runs.count()


class SupplierQuoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierQuote
        fields = [
            "id",
            "supplier_name",
            "unit_price",
            "moq",
            "lead_time_days",
            "tooling_cost",
            "source_url",
            "notes",
            "is_selected",
        ]


class BomLineItemSerializer(serializers.ModelSerializer):
    quotes = SupplierQuoteSerializer(many=True, read_only=True)
    file_name = serializers.SerializerMethodField()

    class Meta:
        model = BomLineItem
        fields = [
            "id",
            "file",
            "file_name",
            "part_name",
            "part_number",
            "material_spec",
            "quantity",
            "status",
            "quotes",
        ]

    def get_file_name(self, obj):
        return obj.file.original_name if obj.file else None


class BomResearchRunSerializer(serializers.ModelSerializer):
    line_items = BomLineItemSerializer(many=True, read_only=True)

    class Meta:
        model = BomResearchRun
        fields = [
            "id",
            "project",
            "status",
            "inputs_json",
            "research_log",
            "results_json",
            "excel_s3_key",
            "line_items",
            "created_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "project",
            "status",
            "research_log",
            "results_json",
            "excel_s3_key",
            "line_items",
            "created_at",
            "completed_at",
        ]


class TeamContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamContact
        fields = [
            "id",
            "full_name",
            "email",
            "role",
            "department",
            "expertise_tags",
            "slack_handle",
            "preferred_channel",
            "notes",
            "allow_automated",
            "added_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "added_by", "created_at", "updated_at"]
