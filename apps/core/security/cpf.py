from __future__ import annotations

import base64
import hashlib
import hmac
import os
import sys

from django.core.exceptions import ImproperlyConfigured

try:
    from cryptography.fernet import Fernet, InvalidToken
except Exception:  # pragma: no cover - dependência opcional até ativar o cutover
    # fallback comum em ambientes Debian/Ubuntu com pacote do sistema instalado
    try:  # pragma: no cover
        sys.path.append("/usr/lib/python3/dist-packages")
        from cryptography.fernet import Fernet, InvalidToken  # type: ignore
    except Exception:  # pragma: no cover
        Fernet = None  # type: ignore[assignment]
        InvalidToken = Exception  # type: ignore[assignment]


class CPFEncryptionUnavailable(ImproperlyConfigured):
    pass


def normalize_cpf(value: str | None) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def mask_cpf(value: str | None) -> str:
    digits = normalize_cpf(value)
    if len(digits) != 11:
        return ""
    return f"***.***.***-{digits[-2:]}"


def cpf_hash(value: str | None, key: str | None = None) -> str:
    digits = normalize_cpf(value)
    if not digits:
        return ""

    hash_key = (key or os.getenv("DJANGO_CPF_HASH_KEY") or "").strip()
    if not hash_key:
        raise ImproperlyConfigured("Defina DJANGO_CPF_HASH_KEY para gerar hash de CPF.")

    return hmac.new(hash_key.encode("utf-8"), digits.encode("utf-8"), hashlib.sha256).hexdigest()


def _fernet_from_key(key: str | None = None):
    if Fernet is None:
        raise CPFEncryptionUnavailable(
            "Dependência 'cryptography' não instalada. Adicione ao ambiente para ativar cifragem de CPF."
        )

    enc_key = (key or os.getenv("DJANGO_CPF_ENCRYPTION_KEY") or "").strip()
    if not enc_key:
        raise ImproperlyConfigured("Defina DJANGO_CPF_ENCRYPTION_KEY para cifrar CPF.")

    fernet_key = base64.urlsafe_b64encode(hashlib.sha256(enc_key.encode("utf-8")).digest())
    return Fernet(fernet_key)


def encrypt_cpf(value: str | None, key: str | None = None) -> str:
    digits = normalize_cpf(value)
    if not digits:
        return ""
    return _fernet_from_key(key).encrypt(digits.encode("utf-8")).decode("utf-8")


def decrypt_cpf(value: str | None, key: str | None = None) -> str:
    token = (value or "").strip()
    if not token:
        return ""

    try:
        digits = _fernet_from_key(key).decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:  # pragma: no cover
        raise ValueError("CPF criptografado inválido ou chave incorreta.") from exc

    return normalize_cpf(digits)


def resolve_cpf_digits(legacy_value: str | None = "", encrypted_value: str | None = "") -> str:
    """
    Prioriza o campo criptografado e cai para o legado em texto puro.
    Não lança erro para evitar quebra de fluxo de negócio.
    """
    if encrypted_value:
        try:
            decrypted = decrypt_cpf(encrypted_value)
            if decrypted:
                return decrypted
        except Exception:
            pass
    return normalize_cpf(legacy_value)


def derive_cpf_security_fields(value: str | None) -> tuple[str, str, str]:
    """
    Retorna (cpf_enc, cpf_hash, cpf_last4) sem quebrar execução quando
    chaves de ambiente ainda não estiverem configuradas.
    """
    digits = normalize_cpf(value)
    if not digits:
        return "", "", ""

    encrypted = ""
    hashed = ""
    last4 = digits[-4:]

    try:
        encrypted = encrypt_cpf(digits)
    except Exception:
        encrypted = ""

    try:
        hashed = cpf_hash(digits)
    except Exception:
        hashed = ""

    return encrypted, hashed, last4
