from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone

MAX_ATTEMPTS = 5
LOCK_MINUTES = 10


def _key(ip: str, codigo: str) -> str:
    return f"loginlock:{ip}:{(codigo or '').lower()}"


def is_locked(ip: str, codigo: str) -> bool:
    data = cache.get(_key(ip, codigo))
    if not data:
        return False
    locked_until = data.get("locked_until")
    return bool(locked_until and locked_until > timezone.now())


def register_failure(ip: str, codigo: str):
    k = _key(ip, codigo)
    data = cache.get(k) or {"count": 0, "locked_until": None}
    data["count"] += 1
    if data["count"] >= MAX_ATTEMPTS:
        data["locked_until"] = timezone.now() + timedelta(minutes=LOCK_MINUTES)
    cache.set(k, data, timeout=LOCK_MINUTES * 60)


def reset(ip: str, codigo: str):
    cache.delete(_key(ip, codigo))
