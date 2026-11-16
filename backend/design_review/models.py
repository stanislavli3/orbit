from django.contrib.auth.models import User
from django.db import models

from files_api.models import UploadedFile
from projects.models import Project


class ProjectMember(models.Model):
    DESIGNER = "designer"
    REVIEWER = "reviewer"
    ROLE_CHOICES = [(DESIGNER, "Designer"), (REVIEWER, "Reviewer")]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="project_memberships")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("project", "user")

    def __str__(self):
        return f"{self.user} ({self.role}) on {self.project}"


class Change(models.Model):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    STATE_CHOICES = [(PENDING, "Pending"), (APPROVED, "Approved"), (REJECTED, "Rejected")]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="changes")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    author = models.ForeignKey(User, on_delete=models.PROTECT, related_name="authored_changes")
    files = models.ManyToManyField(UploadedFile, blank=True, related_name="changes")
    parts = models.JSONField(default=list, blank=True)  # part numbers / occurrence ids
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class ImmutableError(Exception):
    pass


class ChangeEvent(models.Model):
    """Append-only audit trail entry. Rows can be created but never updated or deleted."""

    CREATED = "created"
    APPROVED = "approved"
    REJECTED = "rejected"
    INTERFERENCE_CHECK = "interference_check"
    ACTION_CHOICES = [
        (CREATED, "Created"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
        (INTERFERENCE_CHECK, "Interference check"),
    ]

    change = models.ForeignKey(Change, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="change_events")
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    comment = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ImmutableError("Change events are immutable")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableError("Change events are immutable")


class InterferenceCheck(models.Model):
    change = models.ForeignKey(Change, on_delete=models.CASCADE, related_name="interference_checks")
    run_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="interference_checks")
    changed_part = models.CharField(max_length=255)
    neighbours = models.JSONField(default=list)
    source = models.CharField(max_length=255)
    results = models.JSONField(default=list)
    elapsed_ms = models.FloatField()
    manual_baseline_minutes = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
