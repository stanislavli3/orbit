from django.core.management.base import BaseCommand

from bom_agent.gmail_integration import poll_run_replies
from bom_agent.models import BomResearchRun
from core.jobs import record_failure


class Command(BaseCommand):
    help = "Poll Gmail for replies to sent BOM team-request emails."

    def add_arguments(self, parser):
        parser.add_argument("--run-id", type=int, default=None)

    def handle(self, *args, **options):
        run_id = options["run_id"]
        runs = BomResearchRun.objects.prefetch_related("team_requests").all()
        if run_id is not None:
            runs = runs.filter(pk=run_id)

        total = 0
        for run in runs:
            # One run failing (revoked Gmail token, rate limit) is recorded and
            # alerted, but must not stop the other runs from being polled.
            try:
                answered_ids = poll_run_replies(run)
            except Exception as exc:
                record_failure("email_poll", run.pk, exc)
                self.stderr.write(self.style.ERROR(f"Run {run.id}: poll failed — {exc}"))
                continue
            if answered_ids:
                total += len(answered_ids)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Run {run.id}: answered requests {', '.join(str(value) for value in answered_ids)}"
                    )
                )

        if total == 0:
            self.stdout.write("No new BOM email replies found.")
