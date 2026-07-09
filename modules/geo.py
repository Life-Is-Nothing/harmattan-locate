"""IP geolocation (approximate) via public APIs."""
from __future__ import annotations

from typing import Optional

import requests

from core.logging_setup import get_logger

log = get_logger("hloc.geo")


def geo_from_ip(ip: str) -> dict:
    """Best-effort city/country from public IP (not street-level)."""
    ip = (ip or "").strip()
    if not ip or ip in ("127.0.0.1", "::1") or ip.startswith("192.168.") or ip.startswith("10."):
        return {
            "ip": ip,
            "status": "private",
            "message": "IP locale/privée — pas de géoloc publique",
            "country": None,
            "city": None,
            "lat": None,
            "lon": None,
        }

    # Try ipapi.co then ip-api.com
    for fetcher in (_ipapi, _ip_api):
        try:
            data = fetcher(ip)
            if data:
                return data
        except Exception as e:
            log.warning("geo fetch failed: %s", e)
    return {"ip": ip, "status": "error", "message": "Géolocalisation IP indisponible"}


def _ipapi(ip: str) -> Optional[dict]:
    r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=6, headers={"User-Agent": "HARMATTAN-LOCATE/1.0"})
    if r.status_code != 200:
        return None
    j = r.json()
    if j.get("error"):
        return None
    return {
        "ip": ip,
        "status": "ok",
        "country": j.get("country_name"),
        "country_code": j.get("country_code"),
        "region": j.get("region"),
        "city": j.get("city"),
        "postal": j.get("postal"),
        "org": j.get("org"),
        "lat": j.get("latitude"),
        "lon": j.get("longitude"),
        "timezone": j.get("timezone"),
        "source": "ipapi.co",
        "maps_url": _maps(j.get("latitude"), j.get("longitude")),
    }


def _ip_api(ip: str) -> Optional[dict]:
    r = requests.get(f"http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,regionName,city,zip,lat,lon,timezone,isp,org,query", timeout=6)
    j = r.json()
    if j.get("status") != "success":
        return None
    return {
        "ip": ip,
        "status": "ok",
        "country": j.get("country"),
        "country_code": j.get("countryCode"),
        "region": j.get("regionName"),
        "city": j.get("city"),
        "postal": j.get("zip"),
        "org": j.get("isp") or j.get("org"),
        "lat": j.get("lat"),
        "lon": j.get("lon"),
        "timezone": j.get("timezone"),
        "source": "ip-api.com",
        "maps_url": _maps(j.get("lat"), j.get("lon")),
    }


def _maps(lat, lon) -> Optional[str]:
    if lat is None or lon is None:
        return None
    return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=14/{lat}/{lon}"


def parse_ua(ua: str) -> dict:
    ua = ua or ""
    low = ua.lower()
    device = "desktop"
    if "mobile" in low or "android" in low or "iphone" in low:
        device = "mobile"
    elif "tablet" in low or "ipad" in low:
        device = "tablet"
    browser = "unknown"
    for name, key in (
        ("Edge", "edg/"),
        ("Chrome", "chrome/"),
        ("Firefox", "firefox/"),
        ("Safari", "safari/"),
        ("Opera", "opr/"),
    ):
        if key in low:
            browser = name
            break
    os_name = "unknown"
    for name, key in (
        ("Android", "android"),
        ("iOS", "iphone"),
        ("iOS", "ipad"),
        ("Windows", "windows"),
        ("macOS", "mac os"),
        ("Linux", "linux"),
    ):
        if key in low:
            os_name = name
            break
    return {"device": device, "browser": browser, "os": os_name, "raw": ua[:300]}
