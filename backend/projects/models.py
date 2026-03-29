from django.db import models
from django.contrib.auth.models import User


class Project(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="projects")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ExportLog(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="export_logs")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="export_logs")
    file_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Export by {self.user} on {self.project} at {self.created_at}"
