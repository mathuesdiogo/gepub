import os
from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw.strip())
        return value if value > 0 else default
    except Exception:
        return default


MAX_ATTEMPTS_PER_CODE = _env_int("DJANGO_LOGIN_MAX_ATTEMPTS_PER_CODE", 5)
MAX_ATTEMPTS_PER_IP = _env_int("DJANGO_LOGIN_MAX_ATTEMPTS_PER_IP", 25)
LOCK_MINUTES = _env_int("DJANGO_LOGIN_LOCK_MINUTES", 10)


def _code_key(ip: str, codigo: str) -> str:
    return f"loginlock:{ip}:{(codigo or '').lower()}"


def _ip_key(ip: str) -> str:
    return f"loginlock:ip:{ip}"


def _is_locked_payload(data: dict | None) -> bool:
    if not data:
        return False
    locked_until = data.get("locked_until")
    return bool(locked_until and locked_until > timezone.now())


def _register_on_key(key: str, max_attempts: int):
    data = cache.get(key) or {"count": 0, "locked_until": None}
    data["count"] += 1
    if data["count"] >= max_attempts:
        data["locked_until"] = timezone.now() + timedelta(minutes=LOCK_MINUTES)
    cache.set(key, data, timeout=LOCK_MINUTES * 60)


def is_locked(ip: str, codigo: str) -> bool:
    return _is_locked_payload(cache.get(_code_key(ip, codigo))) or _is_locked_payload(cache.get(_ip_key(ip)))


def register_failure(ip: str, codigo: str):
    _register_on_key(_code_key(ip, codigo), MAX_ATTEMPTS_PER_CODE)
    _register_on_key(_ip_key(ip), MAX_ATTEMPTS_PER_IP)


def reset(ip: str, codigo: str):
    cache.delete(_code_key(ip, codigo))
    cache.delete(_ip_key(ip))
