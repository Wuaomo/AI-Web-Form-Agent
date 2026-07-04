import json
import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)


def emit_metrics_event(event: dict[str, Any]) -> bool:
    """Send an operational event to the optional Go metrics sidecar."""
    sidecar_url = os.getenv("METRICS_SIDECAR_URL", "").strip()

    if not sidecar_url:
        return False

    try:
        response = requests.post(
            f"{sidecar_url}/events",
            json=event,
            timeout=0.5,
        )
        return response.status_code == 202
    except requests.exceptions.RequestException as e:
        logger.warning("Failed to emit metrics event: %s", str(e))
        return False