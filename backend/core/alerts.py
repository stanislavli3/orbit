"""Alert channel for failed background jobs: an optional Slack-style webhook."""

import json
import logging
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger("orbit.jobs")

_TIMEOUT_SECONDS = 5


def send_alert(text: str) -> None:
    """
    POST ``{"text": ...}`` to ``ALERT_WEBHOOK_URL`` (works with Slack incoming
    webhooks and most Slack-compatible services). Does nothing when the URL is
    unset, and never raises: alerting must not break the job that failed.
    """
    url = getattr(settings, "ALERT_WEBHOOK_URL", "")
    if not url:
        return
    try:
        request = Request(
            url,
            data=json.dumps({"text": text}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=_TIMEOUT_SECONDS):
            pass
    except Exception:
        logger.exception("alert_delivery_failed")
