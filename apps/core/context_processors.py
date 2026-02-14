# apps/core/context_processors.py
from __future__ import annotations

from apps.core.rbac import can


def permissions(request):
    """Permissões usadas nos templates (menu/sidebar).

    Mantém as chaves esperadas pelo seu base.html e telas de Educação.
    """
    u = getattr(request, "user", None)
    return {
        "can_org": can(u, "org.view"),
        "can_edu": can(u, "educacao.view"),
        "can_nee": can(u, "nee.view"),
        "can_users": can(u, "accounts.manage_users"),
        "can_edu_manage": can(u, "educacao.manage"),
        "can_org_municipios": can(u, "org.municipios.view") or can(u, "org.manage") or (getattr(u, "is_superuser", False)),
    }
