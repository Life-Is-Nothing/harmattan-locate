"""Push alerts to HARMATTAN-HUB."""
from __future__ import annotations

import os

import requests

from core.logging_setup import get_logger

log = get_logger("hloc.alerts")
HUB_URL = os.environ.get("HARMATTAN_HUB_URL", "http://127.0.0.1:8077")
HUB_TOKEN = os.environ.get("HARMATTAN_HUB_TOKEN", os.environ.get("HHUB_TOKEN", os.environ.get("HLOC_TOKEN", "")))


def notify(text: str) -> None:
    try:
        headers = {"Content-Type": "application/json"}
        if HUB_TOKEN:
            headers["X-Hub-Token"] = HUB_TOKEN
            headers["X-HLOC-Token"] = HUB_TOKEN
        requests.post(
            f"{HUB_URL.rstrip('/')}/api/alert",
            json={"text": text, "source": "locate"},
            headers=headers,
            timeout=3,
        )
    except Exception as e:
        log.debug("alert: %s", e)
