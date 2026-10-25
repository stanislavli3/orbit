from django.db import models


class JobFailure(models.Model):
    """
    Dead-letter record: a background job that failed for good (retries
    exhausted, a non-retryable error, or a crash loop). This table is the one
    place a human looks for failed jobs; see the Django admin.
    """

    job_type = models.CharField(max_length=40, db_index=True)
    target_id = models.CharField(max_length=64, blank=True)
    task_id = models.CharField(max_length=64, blank=True)
    error_class = models.CharField(max_length=200)
    error_message = models.TextField(blank=True)
    traceback = models.TextField(blank=True)
    attempts = models.PositiveIntegerField(default=1)
    # Repeats of the same unresolved failure fold into one row.
    occurrences = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_seen_at"]

    def __str__(self):
        return f"{self.job_type}#{self.target_id}: {self.error_class}"


class JobAttempt(models.Model):
    """
    Starts of a job that haven't finished. A normal exit deletes the row, so a
    row that survives a restart means the worker was killed mid-job. Once the
    count passes the limit the job is dead-lettered instead of run again.
    """

    job_type = models.CharField(max_length=40)
    target_id = models.CharField(max_length=64)
    unfinished_starts = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["job_type", "target_id"], name="unique_job_attempt"
            )
        ]
