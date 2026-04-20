from django.db import models
from django.contrib.auth.models import User


class LibraryDocument(models.Model):
    TYPE_CHOICES = [
        ("avl", "Approved Vendor List"),
        ("material-spec", "Material Specification"),
        ("compliance", "Compliance Document"),
        ("previous-bom", "Previous BOM"),
        ("scorecard", "Supplier Scorecard"),
        ("standard", "Design Standard"),
        ("preferred-materials", "Preferred Materials"),
    ]

    workspace_owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="library_documents"
    )
    original_name = models.CharField(max_length=255)
    doc_type = models.CharField(max_length=30, choices=TYPE_CHOICES, blank=True)
    s3_key = models.CharField(max_length=500, unique=True)
    file_size = models.BigIntegerField()
    file_type = models.CharField(max_length=50, blank=True)
    source_file = models.ForeignKey(
        "files_api.UploadedFile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="library_versions",
    )
    extracted_text = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.original_name} ({self.doc_type})"


class LibraryEmbedding(models.Model):
    document = models.OneToOneField(
        LibraryDocument, on_delete=models.CASCADE, related_name="embedding"
    )
    embedding_json = models.JSONField()
    doc_type = models.CharField(max_length=30, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class BomResearchRun(models.Model):
    STATUS_CHOICES = [
        ("gathering_inputs", "Gathering Inputs"),
        ("researching", "Researching"),
        ("generating_report", "Generating Report"),
        ("awaiting_team_input", "Awaiting Team Input"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="bom_runs"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="bom_runs"
    )
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default="gathering_inputs"
    )
    inputs_json = models.JSONField(default=dict)
    research_log = models.JSONField(default=list)
    results_json = models.JSONField(default=dict)
    excel_s3_key = models.CharField(max_length=500, blank=True)
    library_documents = models.ManyToManyField(
        LibraryDocument, blank=True, related_name="bom_runs"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"BOM Run {self.id} — {self.project} ({self.status})"


class BomLineItem(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("researching", "Researching"),
        ("sourced", "Sourced"),
        ("needs_input", "Needs Input"),
    ]

    run = models.ForeignKey(
        BomResearchRun, on_delete=models.CASCADE, related_name="line_items"
    )
    file = models.ForeignKey(
        "files_api.UploadedFile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bom_line_items",
    )
    part_name = models.CharField(max_length=300)
    part_number = models.CharField(max_length=100, blank=True)
    material_spec = models.CharField(max_length=300, blank=True)
    quantity = models.IntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    class Meta:
        ordering = ["part_name"]

    def __str__(self):
        return f"{self.part_name} (run {self.run_id})"


class SupplierQuote(models.Model):
    line_item = models.ForeignKey(
        BomLineItem, on_delete=models.CASCADE, related_name="quotes"
    )
    supplier_name = models.CharField(max_length=200)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    moq = models.IntegerField()
    lead_time_days = models.IntegerField()
    tooling_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    landed_cost_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    source_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    is_avl = models.BooleanField(default=False)
    is_selected = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.supplier_name} — {self.line_item.part_name}"


class TeamContact(models.Model):
    CHANNEL_CHOICES = [
        ("email", "Email"),
        ("slack", "Slack"),
    ]

    workspace_owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="team_contacts"
    )
    added_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="added_contacts"
    )
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    role = models.CharField(max_length=200)
    department = models.CharField(max_length=200, blank=True)
    expertise_tags = models.JSONField(default=list)
    slack_handle = models.CharField(max_length=100, blank=True)
    preferred_channel = models.CharField(
        max_length=10, choices=CHANNEL_CHOICES, default="email"
    )
    notes = models.TextField(blank=True)
    allow_automated = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("workspace_owner", "email")
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} <{self.email}>"


class GmailCredential(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="gmail_credential"
    )
    gmail_address = models.EmailField()
    encrypted_access_token = models.TextField(blank=True)
    encrypted_refresh_token = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    scopes_json = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"GmailCredential {self.gmail_address}"


class TeamRequest(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("sent", "Sent"),
        ("answered", "Answered"),
        ("follow_up", "Follow-up Sent"),
    ]

    run = models.ForeignKey(
        BomResearchRun, on_delete=models.CASCADE, related_name="team_requests"
    )
    contact = models.ForeignKey(
        TeamContact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="team_requests",
    )
    line_item = models.ForeignKey(
        BomLineItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="team_requests",
    )
    recipient_email = models.EmailField()
    recipient_name = models.CharField(max_length=200)
    question = models.TextField()
    question_key = models.CharField(max_length=200, blank=True)
    channel = models.CharField(
        max_length=10, choices=TeamContact.CHANNEL_CHOICES, default="email"
    )
    email_subject = models.CharField(max_length=500, blank=True)
    email_body = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft"
    )
    response = models.TextField(blank=True)
    gmail_message_id = models.CharField(max_length=255, blank=True)
    gmail_thread_id = models.CharField(max_length=255, blank=True)
    gmail_reply_message_id = models.CharField(max_length=255, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    follow_up_count = models.IntegerField(default=0)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"TeamRequest {self.id} — {self.recipient_email} ({self.status})"
