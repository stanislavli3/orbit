from django.core.management.base import BaseCommand

from bom_agent.rfq_loop import escalate_silent_rfqs, poll_rfq_replies


class Command(BaseCommand):
    help = "Poll Gmail for supplier replies to sent RFQs and escalate silent threads (cron-friendly)."

    def handle(self, *args, **options):
        replied = poll_rfq_replies()
        escalated = escalate_silent_rfqs()
        self.stdout.write(f"RFQ replies processed: {len(replied)}; escalated: {len(escalated)}")
