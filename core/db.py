"""SQLite persistence."""
from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Iterator, Optional

from core.config import DB_PATH, ensure_dirs
from core.logging_setup import get_logger

log = get_logger("hloc.db")
_local = threading.local()
_lock = threading.Lock()
_ready = False


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def get_conn() -> sqlite3.Connection:
    global _ready
    if not getattr(_local, "conn", None):
        _local.conn = _connect()
    if not _ready:
        with _lock:
            if not _ready:
                init_db(_local.conn)
                _ready = True
    return _local.conn


@contextmanager
def cursor() -> Iterator[sqlite3.Cursor]:
    conn = get_conn()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db(conn: Optional[sqlite3.Connection] = None) -> None:
    conn = conn or get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            message TEXT,
            operator_name TEXT,
            active INTEGER DEFAULT 1,
            require_gps INTEGER DEFAULT 1,
            max_clicks INTEGER DEFAULT 0,
            expires_at TEXT,
            password_hash TEXT,
            redirect_url TEXT,
            theme TEXT DEFAULT 'default',
            created TEXT NOT NULL,
            notes TEXT,
            click_count INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_id INTEGER NOT NULL,
            created TEXT NOT NULL,
            event_type TEXT NOT NULL,
            ip TEXT,
            user_agent TEXT,
            language TEXT,
            timezone TEXT,
            referrer TEXT,
            screen TEXT,
            platform TEXT,
            consent_text INTEGER DEFAULT 0,
            consent_gps INTEGER DEFAULT 0,
            lat REAL,
            lon REAL,
            accuracy REAL,
            altitude REAL,
            geo_ip_json TEXT,
            extra_json TEXT,
            FOREIGN KEY(link_id) REFERENCES links(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    conn.commit()
    log.info("DB ready %s", DB_PATH)


def create_link(
    title: str,
    message: str = "",
    operator_name: str = "",
    require_gps: bool = True,
    max_clicks: int = 0,
    expires_hours: int = 0,
    password: str = "",
    redirect_url: str = "",
    theme: str = "default",
    notes: str = "",
) -> dict:
    code = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10]
    exp = None
    if expires_hours and expires_hours > 0:
        exp = (datetime.now() + timedelta(hours=int(expires_hours))).isoformat(timespec="seconds")
    pw = ""
    if password:
        import hashlib
        pw = hashlib.sha256(password.encode()).hexdigest()
    t = now()
    with cursor() as cur:
        cur.execute(
            """INSERT INTO links
            (code, title, message, operator_name, require_gps, max_clicks, expires_at,
             password_hash, redirect_url, theme, created, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                code, title, message, operator_name,
                1 if require_gps else 0, int(max_clicks or 0), exp,
                pw or None, redirect_url or None, theme or "default", t, notes,
            ),
        )
        lid = cur.lastrowid
    return get_link(lid)


def get_link(lid: int) -> Optional[dict]:
    with cursor() as cur:
        cur.execute("SELECT * FROM links WHERE id=?", (lid,))
        r = cur.fetchone()
        return _link(r) if r else None


def get_link_by_code(code: str) -> Optional[dict]:
    with cursor() as cur:
        cur.execute("SELECT * FROM links WHERE code=?", (code,))
        r = cur.fetchone()
        return _link(r) if r else None


def _link(r) -> dict:
    d = dict(r)
    d["active"] = bool(d.get("active"))
    d["require_gps"] = bool(d.get("require_gps"))
    d["has_password"] = bool(d.get("password_hash"))
    return d


def list_links() -> list[dict]:
    with cursor() as cur:
        cur.execute("SELECT * FROM links ORDER BY id DESC")
        return [_link(r) for r in cur.fetchall()]


def set_link_active(lid: int, active: bool) -> None:
    with cursor() as cur:
        cur.execute("UPDATE links SET active=? WHERE id=?", (1 if active else 0, lid))


def delete_link(lid: int) -> None:
    with cursor() as cur:
        cur.execute("DELETE FROM events WHERE link_id=?", (lid,))
        cur.execute("DELETE FROM links WHERE id=?", (lid,))


def check_password(link: dict, password: str) -> bool:
    if not link.get("password_hash"):
        return True
    import hashlib
    return hashlib.sha256((password or "").encode()).hexdigest() == link["password_hash"]


def link_is_valid(link: dict) -> tuple[bool, str]:
    if not link.get("active"):
        return False, "Ce lien a été désactivé par l'opérateur."
    if link.get("expires_at"):
        try:
            if datetime.now() > datetime.fromisoformat(link["expires_at"]):
                return False, "Ce lien a expiré."
        except Exception:
            pass
    max_c = int(link.get("max_clicks") or 0)
    if max_c > 0 and int(link.get("click_count") or 0) >= max_c:
        return False, "Nombre maximum de participations atteint."
    return True, ""


def add_event(link_id: int, event_type: str, data: dict) -> dict:
    t = now()
    with cursor() as cur:
        cur.execute(
            """INSERT INTO events
            (link_id, created, event_type, ip, user_agent, language, timezone, referrer,
             screen, platform, consent_text, consent_gps, lat, lon, accuracy, altitude,
             geo_ip_json, extra_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                link_id, t, event_type,
                data.get("ip"), data.get("user_agent"), data.get("language"),
                data.get("timezone"), data.get("referrer"), data.get("screen"),
                data.get("platform"),
                1 if data.get("consent_text") else 0,
                1 if data.get("consent_gps") else 0,
                data.get("lat"), data.get("lon"), data.get("accuracy"), data.get("altitude"),
                json.dumps(data.get("geo_ip") or {}, default=str),
                json.dumps(data.get("extra") or {}, default=str),
            ),
        )
        eid = cur.lastrowid
        if event_type in ("share", "view", "consent"):
            cur.execute("UPDATE links SET click_count = click_count + 1 WHERE id=?", (link_id,))
    return get_event(eid)


def get_event(eid: int) -> Optional[dict]:
    with cursor() as cur:
        cur.execute("SELECT * FROM events WHERE id=?", (eid,))
        r = cur.fetchone()
        return _event(r) if r else None


def _event(r) -> dict:
    d = dict(r)
    d["consent_text"] = bool(d.get("consent_text"))
    d["consent_gps"] = bool(d.get("consent_gps"))
    try:
        d["geo_ip"] = json.loads(d.get("geo_ip_json") or "{}")
    except Exception:
        d["geo_ip"] = {}
    try:
        d["extra"] = json.loads(d.get("extra_json") or "{}")
    except Exception:
        d["extra"] = {}
    return d


def list_events(link_id: Optional[int] = None, limit: int = 100) -> list[dict]:
    with cursor() as cur:
        if link_id:
            cur.execute(
                "SELECT * FROM events WHERE link_id=? ORDER BY id DESC LIMIT ?",
                (link_id, limit),
            )
        else:
            cur.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
        return [_event(r) for r in cur.fetchall()]


def stats() -> dict:
    with cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM links")
        links = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM events")
        events = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM events WHERE consent_gps=1 AND lat IS NOT NULL")
        gps = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM links WHERE active=1")
        active = cur.fetchone()["c"]
    return {"links": links, "active_links": active, "events": events, "gps_shares": gps}
