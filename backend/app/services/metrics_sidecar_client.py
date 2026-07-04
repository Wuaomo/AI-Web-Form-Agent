import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


def emit_metrics_event(event: dict[str, Any]) -> bool:
    """Send an operational event to the optional Go metrics sidecar.

    Returns False without raising when the sidecar is unavailable or the
    request fails. This function must never propagate exceptions to the
    caller so that metrics emission cannot fail the main workflow.
    """

    sidecar_url = os.getenv("METRICS_SIDECAR_URL", "").strip()

    if not sidecar_url:
        return False

    try:
        url = f"{sidecar_url.rstrip('/')}/events"
        data = json.dumps(event).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=0.5) as response:
            return response.getcode() == 202
    except Exception as e:
        logger.warning("Failed to emit metrics event: %s", str(e))
        return False