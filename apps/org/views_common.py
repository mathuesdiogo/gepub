from __future__ import annotations

from django.http import HttpResponseForbidden

from apps.core.rbac import get_profile, is_admin


def ensure_municipio_scope_or_403(user, municipio_id: int | None):
    if is_admin(user):
        return None
    p = get_profile(user)
    if p and getattr(p, "municipio_id", None) and municipio_id and int(p.municipio_id) != int(municipio_id):
        return HttpResponseForbidden("403 — Fora do seu município.")
    return None


def force_user_municipio_id(user, municipio_id_raw: str) -> str:
    """Se não for admin e tiver municipio_id no perfil, força o filtro."""
    p = get_profile(user)
    if (not is_admin(user)) and p and getattr(p, "municipio_id", None):
        return str(p.municipio_id)
    return municipio_id_raw
