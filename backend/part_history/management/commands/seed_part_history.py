"""Load clearly labelled SAMPLE part costs so estimates can be demoed before real data exists."""

from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from part_history.importer import import_costs
from part_history.models import ImportBatch, Part, Quote, Supplier

SAMPLES = Path(settings.BASE_DIR).parent / "samples"
SAMPLE_SOURCE = "SAMPLE seed data"

# Suppliers on the sample AVL. "SAMPLE Precision Works" is left off on purpose,
# so the shortlist shows a non-approved supplier being excluded.
APPROVED = {
    "SAMPLE Acme Machining": "ISO 9001",
    "SAMPLE Sheetline Fab": "ISO 9001",
    "SAMPLE Fastenal Demo": "ISO 9001",
    "SAMPLE Castworks": "IATF 16949",
}

# (supplier, part number, material, unit price, lead time days, quoted on)
QUOTES = [
    ("SAMPLE Acme Machining", "ORB-1042", "6061-T6", "4.20", 12, "2025-03-04"),
    ("SAMPLE Precision Works", "ORB-1042", "6061-T6", "3.90", 21, "2025-04-11"),
    ("SAMPLE Sheetline Fab", "ORB-1130", "CRS", "2.05", 9, "2025-02-18"),
    ("SAMPLE Fastenal Demo", "SHCS-M6X16", "SS 304", "0.17", 3, "2025-05-02"),
]


class Command(BaseCommand):
    help = "Seed SAMPLE part-cost history for a user (replaces that user's earlier samples)."

    def add_arguments(self, parser):
        parser.add_argument("user", help="Username or email of the workspace owner")

    def handle(self, *args, user, **options):
        owner = User.objects.filter(Q(username=user) | Q(email=user)).first()
        if owner is None:
            raise CommandError(f"No user with username or email '{user}'.")

        ImportBatch.objects.filter(workspace_owner=owner, is_sample=True).delete()
        path = SAMPLES / "part_cost_history_sample.csv"
        report = import_costs(owner, path.read_bytes(), path.name, is_sample=True)

        Quote.objects.filter(workspace_owner=owner, source=SAMPLE_SOURCE).delete()
        for name, certifications in APPROVED.items():
            Supplier.objects.update_or_create(
                workspace_owner=owner,
                name=name,
                defaults={"is_approved": True, "certifications": certifications, "approval_note": "SAMPLE AVL"},
            )
        for name, part_number, material, price, lead, quoted_at in QUOTES:
            supplier, _ = Supplier.objects.get_or_create(workspace_owner=owner, name=name)
            Quote.objects.create(
                workspace_owner=owner,
                supplier=supplier,
                part=Part.objects.get(workspace_owner=owner, part_number=part_number),
                material=material,
                unit_price=price,
                lead_time_days=lead,
                quoted_at=quoted_at,
                program="SAMPLE",
                source=SAMPLE_SOURCE,
            )
        self.stdout.write(
            self.style.SUCCESS(f"Seeded {report['imported_rows']} SAMPLE costs, {len(APPROVED)} approved suppliers "
                f"and {len(QUOTES)} quotes for {owner.username}.")
        )
