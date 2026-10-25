import os

from celery import Celery
from celery.signals import worker_ready

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("orbit")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@worker_ready.connect
def recover_orphaned_jobs(**kwargs):
    """
    Re-queue jobs a killed worker left in flight. Acks-late alone would also
    recover them, but only after the broker's visibility timeout (hours);
    this resumes them as soon as a worker is back.
    """
    from bom_agent.tasks import recover_orphaned_jobs as recover_bom_jobs
    from files_api.tasks import recover_orphaned_jobs as recover_file_jobs

    recover_bom_jobs()
    recover_file_jobs()
