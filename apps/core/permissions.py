from __future__ import annotations
from typing import Literal
from core.rbac import get_profile, is_admin

Action = Literal["view", "manage"]

ROLE_PERMS = {
    "ADMIN": {
        "org": {"view", "manage"},
        "educacao": {"view", "manage"},
        "nee": {"view", "manage"},
        "relatorios": {"view"},
        "accounts": {"view", "manage"},
        "portal_aluno": {"view"},
        "admin": {"view"},
    },
    "MUNICIPAL": {
        "org": {"view", "manage"},
        "educacao": {"view", "manage"},
        "nee": {"view", "manage"},
        "relatorios": {"view"},
        "accounts": {"view", "manage"},
    },
    "SECRETARIA": {
        "org": {"view"},
        "educacao": {"view", "manage"},
        "nee": {"view"},
        "relatorios": {"view"},
    },
    "UNIDADE": {
        "educacao": {"view", "manage"},
        "nee": {"view"},
        "relatorios": {"view"},
    },
    "PROFESSOR": {
        "educacao": {"view"},
    },
    "ALUNO": {
        "portal_aluno": {"view"},
    },
    "LEITURA": {
        "org": {"view"},
        "educacao": {"view"},
        "nee": {"view"},
        "relatorios": {"view"},
    },
}

def can(user, module: str, action: Action = "view") -> bool:
    if not user.is_authenticated:
        return False

    if is_admin(user):
        return True

    p = get_profile(user)
    if not p or not p.ativo:
        return False

    perms = ROLE_PERMS.get(p.role, {})
    return action in perms.get(module, set())
