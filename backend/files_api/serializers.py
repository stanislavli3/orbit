from rest_framework import serializers
from .models import UploadedFile


class UploadedFileSerializer(serializers.ModelSerializer):
    project_name = serializers.SerializerMethodField()

    def get_project_name(self, obj):
        return obj.project.name if obj.project_id else None

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
            "created_at",
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
        ]
