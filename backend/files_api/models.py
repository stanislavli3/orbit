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

    SOURCE_CHOICES = [
        ("upload", "Uploaded"),
        ("local_folder", "Local folder"),
        ("google_drive", "Google Drive"),
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

    # Where the file lives. Uploaded files are copied to S3; connected files are
    # indexed in place and link back to ``external_url``.
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="upload")
    connected_source = models.ForeignKey(
        "ConnectedSource", null=True, blank=True, on_delete=models.CASCADE, related_name="files"
    )
    external_id = models.CharField(max_length=500, blank=True, default="")
    external_url = models.CharField(max_length=1000, blank=True, default="")
    owner_name = models.CharField(max_length=255, blank=True, default="")
    last_editor_name = models.CharField(max_length=255, blank=True, default="")
    source_modified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.original_name


class ConnectedSource(models.Model):
    """A per-project repository that Orbit indexes in place (no copying)."""

    KIND_CHOICES = [
        ("local_folder", "Local folder"),
        ("google_drive", "Google Drive folder"),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="connected_sources"
    )
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    name = models.CharField(max_length=255, blank=True, default="")
    # local_folder: {"path": "/abs/path"}; google_drive: {"folder_id": "..."}
    config = models.JSONField(default=dict)
    last_indexed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    file_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_kind_display()}: {self.name}"


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
