"""Load clearly labelled SAMPLE part costs so estimates can be demoed before real data exists."""

from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from part_history.importer import import_costs
from part_history.models import ImportBatch

SAMPLES = Path(settings.BASE_DIR).parent / "samples"


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
        self.stdout.write(
            self.style.SUCCESS(f"Seeded {report['imported_rows']} SAMPLE costs for {owner.username}.")
        )
