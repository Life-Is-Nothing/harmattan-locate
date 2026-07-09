"""HARMATTAN-LOCATE — Consent-based location sharing platform."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("HLOC_DATA", BASE_DIR / "data"))
DB_PATH = Path(os.environ.get("HLOC_DB", DATA_DIR / "locate.db"))

HOST = os.environ.get("HLOC_HOST", "127.0.0.1")
PORT = int(os.environ.get("HLOC_PORT", "8095"))
# Public base URL for generated links (set to your tunnel/ngrok if remote)
PUBLIC_BASE = os.environ.get("HLOC_PUBLIC_BASE", f"http://{HOST}:{PORT}").rstrip("/")

SECRET_KEY = os.environ.get("HLOC_SECRET", secrets.token_hex(32))
API_TOKEN = os.environ.get("HLOC_TOKEN", "").strip()
AUTO_TOKEN = os.environ.get("HLOC_AUTO_TOKEN", "1") in ("1", "true", "True")

VERSION = "1.0.0"
APP_NAME = "HARMATTAN-LOCATE"
TAGLINE = "Consent-Based Location Sharing Platform"

LEGAL = (
    "Cet outil n'est utilisable qu'avec le consentement éclairé de la personne "
    "qui ouvre le lien. La page affiche clairement qu'il s'agit d'un partage volontaire. "
    "Toute utilisation trompeuse ou sans consentement est interdite et illégale."
)


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
