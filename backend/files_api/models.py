from django.db import models
from django.contrib.auth.models import User
from projects.models import Project


class UploadedFile(models.Model):
    STATUS_CHOICES = [
        ("uploaded", "Uploaded"),
        ("processing", "Processing"),
        ("processed", "Processed"),
        ("failed", "Failed"),
    ]

    CATEGORY_CHOICES = [
        ("vault", "Vault"),
        ("library", "Library"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="files")
    uploaded_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="uploaded_files"
    )
    original_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    file_type = models.CharField(max_length=50, blank=True)
    s3_key = models.CharField(max_length=500, unique=True)
    file_size = models.BigIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="uploaded")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="vault")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_name


class ExtractionResult(models.Model):
    file = models.OneToOneField(
        UploadedFile, on_delete=models.CASCADE, related_name="result"
    )
    result_json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Result for {self.file.original_name}"


class FileEmbedding(models.Model):
    file = models.OneToOneField(
        UploadedFile, on_delete=models.CASCADE, related_name="embedding"
    )
    embedding_json = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Embedding for {self.file.original_name}"
