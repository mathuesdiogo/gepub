# apps/core/context_processors.py
from __future__ import annotations
from core.rbac import can

from .rbac import (
    can,
    get_user_perms,
    PERM_ORG,
    PERM_EDU,
    PERM_NEE,
    PERM_ACCOUNTS,
    PERM_REPORTS,
)


def permissions(request):
    """
    Disponibiliza permissões no template:
      - perms_set: set bruto
      - can_org/can_edu/can_nee/can_accounts/can_reports: booleans
    """
    user = getattr(request, "user", None)
    perms = get_user_perms(user)

    return {
        "perms_set": perms,
        "can_org": can(user, PERM_ORG),
        "can_edu": can(user, PERM_EDU),
        "can_nee": can(user, PERM_NEE),
        "can_accounts": can(user, PERM_ACCOUNTS),
        "can_reports": can(user, PERM_REPORTS),
    }
from core.rbac import can

def permissions(request):
    u = getattr(request, "user", None)

    return {
        # mantém os módulos (essas chaves precisam existir pro seu base.html)
        "can_org": can(u, "org.view"),
        "can_edu": can(u, "educacao.view"),
        "can_nee": can(u, "nee.view"),

        # adiciona usuários
        "can_users": can(u, "accounts.manage_users"),
    }
from core.rbac import can

def permissions(request):
    u = getattr(request, "user", None)
    return {
        "can_org": can(u, "org.view"),
        "can_edu": can(u, "educacao.view"),
        "can_nee": can(u, "nee.view"),
        "can_users": can(u, "accounts.manage_users"),
        "can_edu_manage": can(u, "educacao.manage"),  # <<< ADICIONE ESTA
    }
