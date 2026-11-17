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


class LlmUsage(models.Model):
    """One Claude call: tokens, dollar cost and latency (assignment #23).

    Written by ``core.usage.tracked_create``; summed by ``eval/cogs.py`` into
    cost per extraction / query / agent run / seat (#31).
    """

    PATH_CHOICES = [
        ("extraction", "Extraction"),
        ("query", "Query"),
        ("agent", "Agent"),
        ("enrichment", "Enrichment"),
    ]

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    path = models.CharField(max_length=20, choices=PATH_CHOICES, db_index=True)
    operation = models.CharField(max_length=60)
    model = models.CharField(max_length=80, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cache_creation_input_tokens = models.PositiveIntegerField(default=0)
    cache_read_input_tokens = models.PositiveIntegerField(default=0)
    web_search_requests = models.PositiveIntegerField(default=0)
    # Null when the model has no price in core.usage.PRICES.
    cost_usd = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    user = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    # e.g. "file:12", "bom_run:3/item:9" — what the call was for.
    target = models.CharField(max_length=120, blank=True)
    error = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.path}/{self.operation} {self.model} ${self.cost_usd}"
