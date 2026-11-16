from rest_framework import serializers
from .models import ConnectedSource, UploadedFile


def _display_name(user) -> str:
    if user is None:
        return ""
    return user.get_full_name() or user.email or user.username


class UploadedFileSerializer(serializers.ModelSerializer):
    project_name = serializers.SerializerMethodField()
    owner = serializers.SerializerMethodField()
    last_editor = serializers.SerializerMethodField()
    source_name = serializers.SerializerMethodField()

    def get_project_name(self, obj):
        return obj.project.name if obj.project_id else None

    def get_owner(self, obj):
        # Uploaded files: whoever uploaded them. Connected files: what the source reports.
        if obj.source == "upload":
            return _display_name(obj.uploaded_by)
        return obj.owner_name or None

    def get_last_editor(self, obj):
        if obj.source == "upload":
            return _display_name(obj.uploaded_by)
        return obj.last_editor_name or None

    def get_source_name(self, obj):
        if obj.connected_source_id:
            return obj.connected_source.name or obj.connected_source.get_kind_display()
        return None

    class Meta:
        model = UploadedFile
        fields = [
            "id",
            "project",
            "project_name",
            "uploaded_by",
            "original_name",
            "description",
            "file_type",
            "file_size",
            "status",
            "category",
            "created_at",
            "source",
            "source_name",
            "connected_source",
            "external_url",
            "owner",
            "last_editor",
            "source_modified_at",
        ]
        read_only_fields = [
            "id",
            "uploaded_by",
            "project_name",
            "original_name",
            "file_type",
            "file_size",
            "status",
            "created_at",
            "source",
            "source_name",
            "connected_source",
            "external_url",
            "owner",
            "last_editor",
            "source_modified_at",
        ]


class ConnectedSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConnectedSource
        fields = [
            "id", "project", "kind", "name", "config", "last_indexed_at",
            "last_error", "file_count", "created_at",
        ]
        read_only_fields = ["id", "last_indexed_at", "last_error", "file_count", "created_at"]
