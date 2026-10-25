from rest_framework import serializers
from datetime import timedelta
from .models import (
    TeamContact,
    GmailCredential,
    BomResearchRun,
    BomLineItem,
    SupplierQuote,
    LibraryDocument,
    TeamRequest,
)


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
            "ingest_status",
        ]
        read_only_fields = [
            "id", "original_name", "file_type", "file_size", "uploaded_at", "bom_run_count", "ingest_status",
        ]

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
            "landed_cost_usd",
            "source_url",
            "notes",
            "is_avl",
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


class GmailCredentialSerializer(serializers.ModelSerializer):
    has_refresh_token = serializers.SerializerMethodField()

    class Meta:
        model = GmailCredential
        fields = [
            "id",
            "gmail_address",
            "token_expires_at",
            "scopes_json",
            "has_refresh_token",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "token_expires_at",
            "has_refresh_token",
            "created_at",
            "updated_at",
        ]

    def get_has_refresh_token(self, obj):
        return bool(obj.encrypted_refresh_token)


class TeamRequestSerializer(serializers.ModelSerializer):
    contact = TeamContactSerializer(read_only=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = TeamRequest
        fields = [
            "id",
            "run",
            "contact",
            "line_item",
            "recipient_email",
            "recipient_name",
            "question",
            "question_key",
            "channel",
            "email_subject",
            "email_body",
            "status",
            "response",
            "gmail_message_id",
            "gmail_thread_id",
            "gmail_reply_message_id",
            "approved_at",
            "sent_at",
            "answered_at",
            "follow_up_count",
            "last_checked_at",
            "is_overdue",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "run",
            "contact",
            "line_item",
            "question",
            "question_key",
            "status",
            "response",
            "gmail_message_id",
            "gmail_thread_id",
            "gmail_reply_message_id",
            "approved_at",
            "sent_at",
            "answered_at",
            "follow_up_count",
            "last_checked_at",
            "is_overdue",
            "created_at",
        ]

    def get_is_overdue(self, obj):
        if obj.status != "sent" or not obj.sent_at:
            return False
        from django.utils import timezone

        return obj.sent_at <= timezone.now() - timedelta(hours=48)


class TeamRequestUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamRequest
        fields = [
            "recipient_email",
            "recipient_name",
            "channel",
            "email_subject",
            "email_body",
        ]

    def validate_channel(self, value):
        if value not in {"email", "slack"}:
            raise serializers.ValidationError("Invalid channel.")
        return value

    def update(self, instance, validated_data):
        if instance.status != "draft":
            raise serializers.ValidationError(
                {"detail": "Only draft requests can be edited."}
            )

        request = self.context.get("request")
        recipient_email = validated_data.get("recipient_email")
        if request and recipient_email:
            matched_contact = TeamContact.objects.filter(
                workspace_owner=request.user,
                email=recipient_email,
            ).first()
            instance.contact = matched_contact

        return super().update(instance, validated_data)
