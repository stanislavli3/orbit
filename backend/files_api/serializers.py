from rest_framework import serializers
from .models import UploadedFile


class UploadedFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedFile
        fields = [
            "id",
            "project",
            "uploaded_by",
            "original_name",
            "file_type",
            "file_size",
            "status",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "uploaded_by",
            "original_name",
            "file_type",
            "file_size",
            "status",
            "created_at",
        ]
