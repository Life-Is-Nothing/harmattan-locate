#!/usr/bin/env python3
"""
HARMATTAN-LOCATE — Consent-Based Location Sharing
=================================================
Partage volontaire de position via lien.
La page publique affiche clairement le consentement.
Usage trompeur / sans consentement INTERDIT.

Auteur : NACF / HARMATTAN suite
"""
from __future__ import annotations

import csv
import io
import json
import secrets
from functools import wraps

from flask import Flask, Response, jsonify, redirect, render_template, request, url_for

from core import db
from core.config import (
    API_TOKEN,
    AUTO_TOKEN,
    HOST,
    LEGAL,
    PORT,
    PUBLIC_BASE,
    SECRET_KEY,
    VERSION,
    ensure_dirs,
)
from core.logging_setup import get_logger, setup_logging
from modules.alerts import notify as alert_notify
from modules.geo import geo_from_ip, parse_ua
from modules.rate_limit import allow as rate_allow

setup_logging()
log = get_logger("hloc.app")
ensure_dirs()
db.init_db()

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["JSON_SORT_KEYS"] = False

_RUNTIME_TOKEN = API_TOKEN or (secrets.token_urlsafe(24) if AUTO_TOKEN else "")


def client_ip() -> str:
    # Prefer direct peer; X-Forwarded-For only if you trust reverse proxy
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or ""


@app.before_request
def _auth_ops():
    # Public share pages free
    if request.path.startswith("/s/") or request.path.startswith("/api/public/"):
        return None
    if request.path == "/" or request.path.startswith("/static"):
        return None
    if request.path == "/api/health":
        return None
    if not request.path.startswith("/api") and not request.path.startswith("/ops"):
        return None
    if request.path == "/ops" or request.path.startswith("/ops/"):
        # ops UI uses cookie
        pass
    if not _RUNTIME_TOKEN:
        return None
    if not request.path.startswith("/api"):
        return None
    token = (
        request.headers.get("X-HLOC-Token")
        or request.args.get("token")
        or request.cookies.get("hloc_token")
    )
    if token != _RUNTIME_TOKEN:
        return jsonify({"ok": False, "error": "unauthorized", "message": "Token requis"}), 401
    return None


@app.after_request
def _headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-HLOC-Version"] = VERSION
    if _RUNTIME_TOKEN and request.path in ("/", "/ops"):
        resp.set_cookie("hloc_token", _RUNTIME_TOKEN, httponly=True, samesite="Strict", max_age=86400 * 14)
    return resp


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return redirect(url_for("ops"))


@app.route("/ops")
def ops():
    return render_template(
        "ops.html",
        version=VERSION,
        token=_RUNTIME_TOKEN or "",
        public_base=PUBLIC_BASE,
        legal=LEGAL,
    )


@app.route("/s/<code>")
def share_page(code):
    """Public consent page — always honest about purpose."""
    link = db.get_link_by_code(code)
    if not link:
        return render_template("error.html", message="Lien introuvable."), 404
    ok, msg = db.link_is_valid(link)
    if not ok:
        return render_template("error.html", message=msg), 410
    return render_template(
        "share.html",
        link=link,
        version=VERSION,
        needs_password=link.get("has_password"),
    )


# ---------------------------------------------------------------------------
# Public API (no ops token — called from share page)
# ---------------------------------------------------------------------------
@app.route("/api/public/<code>/meta")
def public_meta(code):
    link = db.get_link_by_code(code)
    if not link:
        return jsonify({"ok": False, "error": "not_found"}), 404
    ok, msg = db.link_is_valid(link)
    return jsonify({
        "ok": ok,
        "message": msg,
        "title": link.get("title"),
        "message_text": link.get("message"),
        "operator_name": link.get("operator_name"),
        "require_gps": link.get("require_gps"),
        "has_password": link.get("has_password"),
        "theme": link.get("theme"),
    })


@app.route("/api/public/<code>/unlock", methods=["POST"])
def public_unlock(code):
    link = db.get_link_by_code(code)
    if not link:
        return jsonify({"ok": False, "error": "not_found"}), 404
    data = request.get_json(force=True, silent=True) or {}
    if not db.check_password(link, data.get("password") or ""):
        return jsonify({"ok": False, "error": "bad_password", "message": "Mot de passe incorrect"}), 403
    return jsonify({"ok": True})


@app.route("/api/public/<code>/submit", methods=["POST"])
def public_submit(code):
    """
    Visitor submits AFTER explicit consent checkboxes on the page.
    consent_text must be true.
    """
    ip = client_ip()
    if not rate_allow(f"submit:{ip}", limit=20, window=60):
        return jsonify({"ok": False, "error": "rate_limited", "message": "Trop de requêtes."}), 429

    link = db.get_link_by_code(code)
    if not link:
        return jsonify({"ok": False, "error": "not_found"}), 404
    ok, msg = db.link_is_valid(link)
    if not ok:
        return jsonify({"ok": False, "error": "invalid", "message": msg}), 410

    data = request.get_json(force=True, silent=True) or {}
    if not data.get("consent_text"):
        return jsonify({
            "ok": False,
            "error": "consent_required",
            "message": "Tu dois accepter explicitement le partage (case à cocher).",
        }), 400

    if link.get("has_password") and not db.check_password(link, data.get("password") or ""):
        return jsonify({"ok": False, "error": "bad_password"}), 403

    ua = request.headers.get("User-Agent", "")
    ua_info = parse_ua(ua)
    geo_ip = geo_from_ip(ip)

    lat = data.get("lat")
    lon = data.get("lon")
    try:
        lat = float(lat) if lat is not None else None
        lon = float(lon) if lon is not None else None
    except (TypeError, ValueError):
        lat = lon = None

    consent_gps = bool(data.get("consent_gps") and lat is not None and lon is not None)
    if link.get("require_gps") and not consent_gps:
        event_type = "partial"
    else:
        event_type = "share"

    event = db.add_event(link["id"], event_type, {
        "ip": ip,
        "user_agent": ua,
        "language": data.get("language") or request.headers.get("Accept-Language", "")[:80],
        "timezone": data.get("timezone"),
        "referrer": data.get("referrer") or request.referrer,
        "screen": data.get("screen"),
        "platform": data.get("platform") or ua_info.get("os"),
        "consent_text": True,
        "consent_gps": consent_gps,
        "lat": lat,
        "lon": lon,
        "accuracy": data.get("accuracy"),
        "altitude": data.get("altitude"),
        "geo_ip": geo_ip,
        "extra": {
            "ua_info": ua_info,
            "maps_gps": (
                f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}"
                if lat is not None and lon is not None else None
            ),
            "note": data.get("note"),
        },
    })

    log.info("Share event link=%s ip=%s gps=%s", code, ip, consent_gps)
    alert_notify(
        f"📍 Partage '{link.get('title')}' — IP {ip} "
        f"({geo_ip.get('city') or '?'}, {geo_ip.get('country') or '?'}) "
        f"GPS={'oui' if consent_gps else 'non'}"
    )

    result = {
        "ok": True,
        "event_id": event["id"],
        "message": "Merci — ton partage volontaire a bien été enregistré.",
        "redirect_url": link.get("redirect_url") or None,
        "summary": {
            "ip_approx": {
                "city": geo_ip.get("city"),
                "country": geo_ip.get("country"),
            },
            "gps_received": consent_gps,
        },
    }
    return jsonify(result)


@app.route("/api/public/<code>/beacon", methods=["POST"])
def public_beacon(code):
    """Light open event (page view) — still after page load of consent UI."""
    link = db.get_link_by_code(code)
    if not link:
        return jsonify({"ok": False}), 404
    ok, _ = db.link_is_valid(link)
    if not ok:
        return jsonify({"ok": False}), 410
    ip = client_ip()
    ua = request.headers.get("User-Agent", "")
    db.add_event(link["id"], "view", {
        "ip": ip,
        "user_agent": ua,
        "language": request.headers.get("Accept-Language", "")[:80],
        "referrer": request.referrer,
        "consent_text": False,
        "consent_gps": False,
        "geo_ip": geo_from_ip(ip),
        "extra": {"ua_info": parse_ua(ua)},
    })
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Operator API
# ---------------------------------------------------------------------------
@app.route("/api/health")
def health():
    return jsonify({"ok": True, "version": VERSION})


@app.route("/api/stats")
def api_stats():
    return jsonify(db.stats())


@app.route("/api/links", methods=["GET"])
def api_links():
    links = db.list_links()
    for L in links:
        L["url"] = f"{PUBLIC_BASE}/s/{L['code']}"
    return jsonify({"links": links})


@app.route("/api/links", methods=["POST"])
def api_links_create():
    data = request.get_json(force=True, silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"ok": False, "error": "missing_title", "message": "Titre requis"}), 400
    # Force honest default message if empty
    message = (data.get("message") or "").strip() or (
        "Cette page te demande de partager volontairement ta position approximative "
        "(et GPS si tu acceptes) avec l'opérateur indiqué ci-dessous, pour un test / démonstration."
    )
    # Block known scam phrases in title/message
    banned = ("argent gratuit", "gagne de l'argent", "free money", "crypto airdrop", "you won", "tu as gagné")
    blob = (title + " " + message).lower()
    if any(b in blob for b in banned):
        return jsonify({
            "ok": False,
            "error": "deceptive_content",
            "message": "Contenu trompeur interdit. Utilise un message honnête de consentement.",
        }), 400

    link = db.create_link(
        title=title,
        message=message,
        operator_name=(data.get("operator_name") or "").strip() or "Opérateur",
        require_gps=bool(data.get("require_gps", True)),
        max_clicks=int(data.get("max_clicks") or 0),
        expires_hours=int(data.get("expires_hours") or 0),
        password=data.get("password") or "",
        redirect_url=(data.get("redirect_url") or "").strip(),
        theme=data.get("theme") or "default",
        notes=data.get("notes") or "",
    )
    link["url"] = f"{PUBLIC_BASE}/s/{link['code']}"
    return jsonify({"ok": True, "data": link})


@app.route("/api/links/<int:lid>", methods=["GET"])
def api_link_get(lid):
    link = db.get_link(lid)
    if not link:
        return jsonify({"ok": False, "error": "not_found"}), 404
    link["url"] = f"{PUBLIC_BASE}/s/{link['code']}"
    events = db.list_events(lid, limit=100)
    return jsonify({"link": link, "events": events})


@app.route("/api/links/<int:lid>/toggle", methods=["POST"])
def api_link_toggle(lid):
    link = db.get_link(lid)
    if not link:
        return jsonify({"ok": False, "error": "not_found"}), 404
    db.set_link_active(lid, not link["active"])
    return jsonify({"ok": True, "active": not link["active"]})


@app.route("/api/links/<int:lid>", methods=["DELETE"])
def api_link_del(lid):
    db.delete_link(lid)
    return jsonify({"ok": True})


@app.route("/api/events")
def api_events():
    lid = request.args.get("link_id", type=int)
    return jsonify({"events": db.list_events(lid, limit=150)})


@app.route("/api/events/export.csv")
def api_export_csv():
    lid = request.args.get("link_id", type=int)
    events = db.list_events(lid, limit=2000)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "id", "link_id", "created", "event_type", "ip", "city", "country",
        "lat", "lon", "accuracy", "consent_gps", "device", "browser", "os", "user_agent",
    ])
    for e in events:
        ua = (e.get("extra") or {}).get("ua_info") or {}
        geo = e.get("geo_ip") or {}
        w.writerow([
            e.get("id"), e.get("link_id"), e.get("created"), e.get("event_type"),
            e.get("ip"), geo.get("city"), geo.get("country"),
            e.get("lat"), e.get("lon"), e.get("accuracy"), e.get("consent_gps"),
            ua.get("device"), ua.get("browser"), ua.get("os"), e.get("user_agent"),
        ])
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=locate_events.csv"},
    )


@app.route("/api/events/export.json")
def api_export_json():
    lid = request.args.get("link_id", type=int)
    events = db.list_events(lid, limit=2000)
    return Response(
        json.dumps({"exported": db.now(), "events": events}, indent=2, default=str),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=locate_events.json"},
    )


@app.route("/api/system")
def api_system():
    return jsonify({
        "version": VERSION,
        "public_base": PUBLIC_BASE,
        "auth_enabled": bool(_RUNTIME_TOKEN),
        "legal": LEGAL,
        "stats": db.stats(),
    })


@app.route("/api/links/<int:lid>/qr")
def api_link_qr(lid):
    """PNG QR code for share URL."""
    link = db.get_link(lid)
    if not link:
        return jsonify({"ok": False, "error": "not_found"}), 404
    url = f"{PUBLIC_BASE}/s/{link['code']}"
    try:
        import qrcode
        img = qrcode.make(url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return Response(buf.getvalue(), mimetype="image/png")
    except Exception:
        # fallback SVG-ish as text QR via API free alternative: return URL only
        return jsonify({"ok": True, "url": url, "message": "Installe qrcode: pip install qrcode pillow"})


@app.route("/api/events/geojson")
def api_events_geojson():
    """GeoJSON for Leaflet map (GPS points + IP approx)."""
    lid = request.args.get("link_id", type=int)
    events = db.list_events(lid, limit=300)
    features = []
    for e in events:
        lat, lon = e.get("lat"), e.get("lon")
        if lat is None or lon is None:
            geo = e.get("geo_ip") or {}
            lat, lon = geo.get("lat"), geo.get("lon")
        if lat is None or lon is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
            "properties": {
                "id": e.get("id"),
                "type": e.get("event_type"),
                "ip": e.get("ip"),
                "created": e.get("created"),
                "gps": bool(e.get("consent_gps") and e.get("lat") is not None),
            },
        })
    return jsonify({"type": "FeatureCollection", "features": features})


if __name__ == "__main__":
    print("=" * 64)
    print(f"  HARMATTAN-LOCATE v{VERSION}")
    print(f"  Dashboard opérateur : http://{HOST}:{PORT}/ops")
    print("  ⚠  Consentement explicite obligatoire — pas de leurre")
    if _RUNTIME_TOKEN:
        print(f"  API Token : {_RUNTIME_TOKEN}")
    print(f"  Liens publics : {PUBLIC_BASE}/s/<code>")
    print("=" * 64)
    log.info("Starting on %s:%s", HOST, PORT)
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
