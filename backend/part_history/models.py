"""Part, price, supplier and quote history across programs (SCRUM-28).

Every row is scoped to a workspace owner, like the Library. Program and model
year are plain fields so imported spreadsheets map onto them directly.
"""

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Part(models.Model):
    """A part number's identity across programs; costs and quotes hang off it."""

    workspace_owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="parts")
    part_number = models.CharField(max_length=100)
    description = models.CharField(max_length=500, blank=True)
    material = models.CharField(max_length=200, blank=True)
    process = models.CharField(max_length=100, blank=True)
    dimensions = models.CharField(max_length=200, blank=True, help_text='e.g. "120 x 40 x 3 mm"')
    mass = models.CharField(max_length=100, blank=True, help_text='e.g. "0.12 kg"')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["part_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace_owner", "part_number"], name="unique_part_number_per_workspace"
            )
        ]
        indexes = [models.Index(fields=["workspace_owner", "material"])]

    def __str__(self):
        return self.part_number


class Supplier(models.Model):
    workspace_owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="suppliers")
    name = models.CharField(max_length=200)
    contact_email = models.EmailField(blank=True)
    certifications = models.CharField(max_length=300, blank=True, help_text="Comma-separated, e.g. ISO 9001, AS9100")
    is_approved = models.BooleanField(default=False, help_text="On the approved vendor list")
    approval_note = models.CharField(max_length=200, blank=True, help_text="Where the approval comes from")

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["workspace_owner", "name"], name="unique_supplier_per_workspace")
        ]

    def __str__(self):
        return self.name


class Quote(models.Model):
    """A price a supplier gave for a part or material, from any source."""

    workspace_owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="quotes")
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="quotes")
    part = models.ForeignKey(Part, null=True, blank=True, on_delete=models.SET_NULL, related_name="quotes")
    material = models.CharField(max_length=200, blank=True)
    tolerance = models.CharField(max_length=100, blank=True)
    certifications = models.CharField(max_length=300, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=4)
    currency = models.CharField(max_length=3, default="USD")
    quantity = models.PositiveIntegerField(null=True, blank=True)
    lead_time_days = models.PositiveIntegerField(null=True, blank=True)
    program = models.CharField(max_length=200, blank=True)
    quoted_at = models.DateField(default=timezone.localdate)
    source = models.CharField(max_length=300, help_text='e.g. "BOM research run #3"')
    import_batch = models.ForeignKey(
        "ImportBatch", null=True, blank=True, on_delete=models.CASCADE, related_name="quotes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-quoted_at", "-id"]
        indexes = [
            models.Index(fields=["workspace_owner", "material"]),
            models.Index(fields=["part", "quoted_at"]),
        ]

    def __str__(self):
        return f"{self.supplier} — {self.unit_price} {self.currency}"


class ImportBatch(models.Model):
    """One uploaded cost spreadsheet. Deleting it removes the costs it added."""

    workspace_owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cost_imports")
    uploaded_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    KIND_CHOICES = [("cost", "Historical part costs"), ("spend", "Supplier spend / invoices")]

    filename = models.CharField(max_length=255)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default="cost")
    total_rows = models.PositiveIntegerField(default=0)
    imported_rows = models.PositiveIntegerField(default=0)
    rejected_rows = models.PositiveIntegerField(default=0)
    rejected_json = models.JSONField(default=list, help_text="Validation report: row number, errors, values")
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.filename} ({self.imported_rows} imported, {self.rejected_rows} rejected)"


class HistoricalCost(models.Model):
    """What a part cost on a past program, e.g. from a cost spreadsheet."""

    workspace_owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="historical_costs")
    part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name="costs")
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4)
    currency = models.CharField(max_length=3, default="USD")
    program = models.CharField(max_length=200, blank=True)
    model_year = models.PositiveSmallIntegerField(null=True, blank=True)
    supplier = models.ForeignKey(
        Supplier, null=True, blank=True, on_delete=models.SET_NULL, related_name="historical_costs"
    )
    source = models.CharField(max_length=300, help_text='e.g. "costs_2022.xlsx row 14"')
    is_sample = models.BooleanField(default=False, help_text="Seeded demo data, not real costs")
    import_batch = models.ForeignKey(
        ImportBatch, null=True, blank=True, on_delete=models.CASCADE, related_name="costs"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-model_year", "-id"]
        indexes = [
            models.Index(fields=["part", "model_year"]),
            models.Index(fields=["workspace_owner", "program"]),
        ]

    def __str__(self):
        return f"{self.part} {self.unit_cost} ({self.program or self.model_year})"


class SupplierResearch(models.Model):
    """An UNVERIFIED look beyond the approved list for one BOM line (SCRUM-70).

    Results never create Suppliers and never touch the AVL; they are kept
    apart from the approved shortlist so nobody mistakes them for vetted data.
    """

    workspace_owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="supplier_research")
    bom_row = models.ForeignKey("bom_agent.BomRow", on_delete=models.CASCADE, related_name="supplier_research")
    mode = models.CharField(max_length=10, help_text='"web" (Claude + web_search) or "history" (no API key)')
    note = models.CharField(max_length=300, blank=True)
    results_json = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class WorkspaceSource(models.Model):
    """A system, folder or list Orbit pulls data from (SCRUM-52).

    Generic per-user source settings. Connectors (local folder, Google Drive,
    PLM exports...) register here by ``kind`` and keep their own settings in
    ``config``; Orbit only reads from sources that are ``enabled``. New
    connectors extend ``KIND_CHOICES`` and read their own ``config`` keys.
    """

    KIND_CHOICES = [
        ("local_folder", "Local / watched folder"),
        ("google_drive", "Google Drive folder"),
        ("cost_import", "Cost-history import"),
        ("supplier_list", "Supplier list / AVL"),
        ("plm", "PLM / CAD system"),
        ("other", "Other"),
    ]

    workspace_owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="workspace_sources")
    kind = models.CharField(max_length=30, choices=KIND_CHOICES)
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=500, blank=True, help_text="Folder path, Drive folder id or URL")
    config = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["kind", "name"]
        constraints = [
            models.UniqueConstraint(fields=["workspace_owner", "kind", "name"], name="unique_source_per_workspace")
        ]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.name}"


class HandoffStep(models.Model):
    """When a CAD-to-quote handoff step happened for a BOM, or for one part on it (SCRUM-75).

    A blank ``part_number`` means the step applies to the whole BOM (e.g. the
    BOM was shared); parts without their own time for a step inherit it.
    """

    STEPS = [
        ("cad_finished", "CAD finished"),
        ("bom_shared", "BOM shared"),
        ("shortlist_ready", "Shortlist ready"),
        ("quote_received", "Quote received"),
        ("quote_accepted", "Quote accepted"),
    ]

    workspace_owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="handoff_steps")
    bom = models.ForeignKey("bom_agent.Bom", on_delete=models.CASCADE, related_name="handoff_steps")
    part_number = models.CharField(max_length=100, blank=True)
    step = models.CharField(max_length=20, choices=STEPS)
    at = models.DateTimeField()
    is_manual = models.BooleanField(default=False)

    class Meta:
        ordering = ["at"]
        constraints = [
            models.UniqueConstraint(fields=["bom", "part_number", "step"], name="unique_handoff_step")
        ]

    def __str__(self):
        return f"{self.bom_id} {self.part_number or '(BOM)'} {self.step} {self.at:%Y-%m-%d}"
