from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Set

from django.contrib.auth.models import AnonymousUser


# Permissões “da aplicação” (não são as permissões nativas do Django)
# A ideia é simples:
# - view: pode ver/listar/detalhar
# - edit: pode criar/editar
# - reports: pode acessar relatórios (nee/educacao)
# - manage_users: pode gerenciar usuários no painel do sistema
# - django_admin: pode ver o link do /admin/ (staff/superuser)
PERM_CORE_DASH = "core.dashboard"

PERM_ORG_VIEW = "org.view"
PERM_ORG_EDIT = "org.edit"

PERM_EDU_VIEW = "educacao.view"
PERM_EDU_EDIT = "educacao.edit"

PERM_NEE_VIEW = "nee.view"
PERM_NEE_EDIT = "nee.edit"
PERM_NEE_REPORTS = "nee.reports"

PERM_ACCOUNTS_PROFILE = "accounts.profile"
PERM_ACCOUNTS_MANAGE = "accounts.manage_users"
PERM_DJANGO_ADMIN = "admin.django"

PERM_ALUNO_PORTAL = "portal.aluno"


def get_profile(user):
    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return None
    return getattr(user, "profile", None)


def is_admin(user) -> bool:
    """
    Admin “geral” do sistema:
    - superuser/staff do Django
    - ou Profile.role == ADMIN
    """
    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return False
    p = get_profile(user)
    return bool(user.is_superuser or user.is_staff or (p and p.role == "ADMIN"))


# ✅ MATRIZ DE PERMISSÕES (ajustável)
ROLE_PERMS: Dict[str, Set[str]] = {
    # ADMIN: vê tudo (o middleware ainda respeita “login_required”)
    "ADMIN": {
        PERM_CORE_DASH,
        PERM_ORG_VIEW, PERM_ORG_EDIT,
        PERM_EDU_VIEW, PERM_EDU_EDIT,
        PERM_NEE_VIEW, PERM_NEE_EDIT, PERM_NEE_REPORTS,
        PERM_ACCOUNTS_PROFILE, PERM_ACCOUNTS_MANAGE,
        PERM_DJANGO_ADMIN,
        PERM_ALUNO_PORTAL,  # admin pode simular/entrar pra testar
    },

    # Prefeitura / Municipal (gestão do município)
    "MUNICIPAL": {
        PERM_CORE_DASH,
        PERM_ORG_VIEW, PERM_ORG_EDIT,
        PERM_EDU_VIEW, PERM_EDU_EDIT,
        PERM_NEE_VIEW, PERM_NEE_REPORTS,  # vê NEE e relatórios (editar tipos pode ser só admin/nee)
        PERM_ACCOUNTS_PROFILE, PERM_ACCOUNTS_MANAGE,
    },

    # Secretaria (gestão educação dentro do município)
    "SECRETARIA": {
        PERM_CORE_DASH,
        PERM_ORG_VIEW,  # normalmente precisa ver org (unidades/secretarias), mas não necessariamente editar município
        PERM_EDU_VIEW, PERM_EDU_EDIT,
        PERM_NEE_VIEW, PERM_NEE_REPORTS,
        PERM_ACCOUNTS_PROFILE,
    },

    # Unidade (escola/creche)
    "UNIDADE": {
        PERM_CORE_DASH,
        PERM_ORG_VIEW,
        PERM_EDU_VIEW, PERM_EDU_EDIT,
        PERM_NEE_VIEW, PERM_NEE_REPORTS,
        PERM_ACCOUNTS_PROFILE,
    },

    # NEE (equipe de necessidades especiais)
    "NEE": {
        PERM_CORE_DASH,
        PERM_EDU_VIEW,
        PERM_NEE_VIEW, PERM_NEE_EDIT, PERM_NEE_REPORTS,
        PERM_ACCOUNTS_PROFILE,
    },

    # Leitura / Observador (somente consultas)
    "LEITURA": {
        PERM_CORE_DASH,
        PERM_ORG_VIEW,
        PERM_EDU_VIEW,
        PERM_NEE_VIEW, PERM_NEE_REPORTS,
        PERM_ACCOUNTS_PROFILE,
    },

    # Aluno
    "ALUNO": {
        PERM_CORE_DASH,
        PERM_ACCOUNTS_PROFILE,
        PERM_ALUNO_PORTAL,
    },
}


def get_user_perms(user) -> Set[str]:
    """
    Retorna o set de permissões RBAC do usuário.
    """
    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return set()

    # staff/superuser sempre tem tudo (ADMIN)
    if user.is_superuser or user.is_staff:
        return set(ROLE_PERMS["ADMIN"])

    p = get_profile(user)
    if not p or not p.ativo:
        return set()

    return set(ROLE_PERMS.get(p.role, set()))


def can(user, perm: str) -> bool:
    """
    Checa se o usuário tem uma permissão RBAC.
    """
    perms = get_user_perms(user)
    return perm in perms


# -----------------------------------
# Helpers para template (perms.org.view etc)
# -----------------------------------
@dataclass
class _Node:
    __dict__: dict


def _tree_from_perms(perms: Set[str]) -> object:
    """
    Gera um objeto acessável por ponto:
      perms.org.view -> True/False
    """
    tree = {
        "core": {"dashboard": PERM_CORE_DASH in perms},
        "org": {"view": PERM_ORG_VIEW in perms, "edit": PERM_ORG_EDIT in perms},
        "educacao": {"view": PERM_EDU_VIEW in perms, "edit": PERM_EDU_EDIT in perms},
        "nee": {"view": PERM_NEE_VIEW in perms, "edit": PERM_NEE_EDIT in perms, "reports": PERM_NEE_REPORTS in perms},
        "accounts": {"profile": PERM_ACCOUNTS_PROFILE in perms, "manage": PERM_ACCOUNTS_MANAGE in perms},
        "admin": {"django": PERM_DJANGO_ADMIN in perms},
        "portal": {"aluno": PERM_ALUNO_PORTAL in perms},
    }

    # transforma dict->obj (dot access)
    root = _Node({})
    for k, v in tree.items():
        setattr(root, k, _Node(v))
    return root
