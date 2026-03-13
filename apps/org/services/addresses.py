from __future__ import annotations

import json
import os
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen


DEFAULT_GEOCODE_PROVIDER = "osm"
DEFAULT_TIMEOUT_SECONDS = 6


def normalize_address_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload or {})

    text_fields = [
        "label",
        "cep",
        "logradouro",
        "numero",
        "complemento",
        "bairro",
        "cidade",
        "estado",
        "pais",
        "reference_point",
        "coverage_area",
        "opening_hours",
    ]
    for field in text_fields:
        data[field] = str(data.get(field, "") or "").strip()

    if not data["label"]:
        data["label"] = "Principal"
    if not data["numero"]:
        data["numero"] = "S/N"

    data["estado"] = data["estado"].upper()
    data["pais"] = (data["pais"] or "BR").upper()[:2] or "BR"

    cep_digits = "".join(ch for ch in data["cep"] if ch.isdigit())
    if cep_digits:
        data["cep"] = f"{cep_digits[:5]}-{cep_digits[5:]}" if len(cep_digits) == 8 else data["cep"]

    data["latitude"] = _to_decimal(data.get("latitude"))
    data["longitude"] = _to_decimal(data.get("longitude"))

    data["is_primary"] = _to_bool(data.get("is_primary"), default=False)
    data["is_public"] = _to_bool(data.get("is_public"), default=True)
    data["is_active"] = _to_bool(data.get("is_active"), default=True)
    return data


def build_address_query(data: Mapping[str, Any]) -> str:
    parts = [
        str(data.get("logradouro") or "").strip(),
        str(data.get("numero") or "").strip(),
        str(data.get("bairro") or "").strip(),
        str(data.get("cidade") or "").strip(),
        str(data.get("estado") or "").strip().upper(),
        str(data.get("cep") or "").strip(),
        "Brasil" if (str(data.get("pais") or "BR").strip().upper() == "BR") else str(data.get("pais") or "").strip(),
    ]
    return ", ".join(part for part in parts if part)


def build_maps_url(latitude, longitude, address_query: str) -> str:
    if latitude is not None and longitude is not None:
        return f"https://www.google.com/maps?q={latitude},{longitude}"
    query = quote_plus(address_query or "")
    return f"https://www.google.com/maps/search/?api=1&query={query}" if query else ""


def build_directions_url(latitude, longitude, address_query: str) -> str:
    if latitude is not None and longitude is not None:
        return f"https://www.google.com/maps/dir/?api=1&destination={latitude},{longitude}"
    query = quote_plus(address_query or "")
    return f"https://www.google.com/maps/dir/?api=1&destination={query}" if query else ""


def geocode_address(data: Mapping[str, Any], provider: str | None = None) -> dict[str, Any]:
    query = build_address_query(data)
    if not query:
        return {
            "ok": False,
            "provider": provider or _provider_from_env(),
            "error": "endereco_vazio",
        }

    configured = (provider or _provider_from_env()).strip().lower() or DEFAULT_GEOCODE_PROVIDER

    if configured == "google":
        result = _geocode_google(query)
        if result.get("ok"):
            return result
        if result.get("error") != "google_key_missing":
            return result

    return _geocode_osm(query)


def _provider_from_env() -> str:
    return (os.getenv("GEPUB_GEOCODE_PROVIDER", DEFAULT_GEOCODE_PROVIDER) or DEFAULT_GEOCODE_PROVIDER).strip().lower()


def _timeout_from_env() -> int:
    raw = (os.getenv("GEPUB_GEOCODE_TIMEOUT_SECONDS", "") or "").strip()
    if raw.isdigit():
        return max(2, min(30, int(raw)))
    return DEFAULT_TIMEOUT_SECONDS


def _geocode_google(query: str) -> dict[str, Any]:
    key = (os.getenv("GOOGLE_GEOCODING_API_KEY", "") or "").strip()
    if not key:
        return {"ok": False, "provider": "google", "error": "google_key_missing"}

    params = urlencode({"address": query, "key": key})
    url = f"https://maps.googleapis.com/maps/api/geocode/json?{params}"
    timeout = _timeout_from_env()

    try:
        req = Request(url, headers={"User-Agent": _user_agent()})
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        status = str(data.get("status") or "").upper()
        if status != "OK":
            return {"ok": False, "provider": "google", "error": status or "google_failed"}

        results = data.get("results") or []
        if not results:
            return {"ok": False, "provider": "google", "error": "google_no_results"}

        loc = ((results[0] or {}).get("geometry") or {}).get("location") or {}
        lat = _to_decimal(loc.get("lat"))
        lng = _to_decimal(loc.get("lng"))
        if lat is None or lng is None:
            return {"ok": False, "provider": "google", "error": "google_invalid_coordinates"}

        return {
            "ok": True,
            "provider": "google",
            "latitude": lat,
            "longitude": lng,
            "raw_status": status,
        }
    except Exception as exc:
        return {"ok": False, "provider": "google", "error": f"google_exception:{exc.__class__.__name__}"}


def _geocode_osm(query: str) -> dict[str, Any]:
    params = urlencode({"q": query, "format": "json", "limit": 1, "countrycodes": "br"})
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    timeout = _timeout_from_env()

    try:
        req = Request(
            url,
            headers={
                "User-Agent": _user_agent(),
                "Accept": "application/json",
            },
        )
        with urlopen(req, timeout=timeout) as resp:
            rows = json.loads(resp.read().decode("utf-8"))

        if not rows:
            return {"ok": False, "provider": "osm", "error": "osm_no_results"}

        row = rows[0] or {}
        lat = _to_decimal(row.get("lat"))
        lng = _to_decimal(row.get("lon"))
        if lat is None or lng is None:
            return {"ok": False, "provider": "osm", "error": "osm_invalid_coordinates"}

        return {
            "ok": True,
            "provider": "osm",
            "latitude": lat,
            "longitude": lng,
        }
    except Exception as exc:
        return {"ok": False, "provider": "osm", "error": f"osm_exception:{exc.__class__.__name__}"}


def _to_decimal(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _user_agent() -> str:
    return (
        (os.getenv("GEPUB_GEOCODE_USER_AGENT", "") or "").strip()
        or "GEPUB/1.0 (gepub@localhost)"
    )


def _to_bool(value, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    val = str(value).strip().lower()
    if val in {"1", "true", "yes", "on", "sim"}:
        return True
    if val in {"0", "false", "no", "off", "nao", "não"}:
        return False
    return default
