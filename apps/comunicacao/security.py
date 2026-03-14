from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

try:
    from cryptography.fernet import Fernet, InvalidToken
except Exception:  # pragma: no cover
    try:  # pragma: no cover
        sys.path.append("/usr/lib/python3/dist-packages")
        from cryptography.fernet import Fernet, InvalidToken  # type: ignore
    except Exception:  # pragma: no cover
        Fernet = None  # type: ignore[assignment]
        InvalidToken = Exception  # type: ignore[assignment]


def _credentials_key() -> str:
    explicit = (os.getenv("DJANGO_COMUNICACAO_CREDENTIALS_KEY") or "").strip()
    if explicit:
        return explicit
    fallback = (getattr(settings, "SECRET_KEY", "") or "").strip()
    if not fallback:
        raise ImproperlyConfigured(
            "Defina DJANGO_COMUNICACAO_CREDENTIALS_KEY ou SECRET_KEY para cifrar credenciais de comunicação."
        )
    return fallback


def _fernet() -> Fernet:
    if Fernet is None:
        raise ImproperlyConfigured("Dependência 'cryptography' não instalada.")
    digest = hashlib.sha256(_credentials_key().encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_credentials_payload(payload: dict[str, Any] | None) -> str:
    source = payload if isinstance(payload, dict) else {}
    if not source:
        return ""
    raw = json.dumps(source, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return _fernet().encrypt(raw).decode("utf-8")


def decrypt_credentials_payload(token: str | None) -> dict[str, Any]:
    text = (token or "").strip()
    if not text:
        return {}
    try:
        raw = _fernet().decrypt(text.encode("utf-8"))
    except InvalidToken as exc:
        raise ValueError("Credenciais cifradas inválidas ou chave incorreta.") from exc
    data = json.loads(raw.decode("utf-8") or "{}")
    if isinstance(data, dict):
        return data
    return {}
