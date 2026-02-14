# apps/core/rbac.py
from __future__ import annotations

from django.db.models import Exists, OuterRef


# =========================
# PERFIL / ADMIN
# =========================
def get_profile(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    return getattr(user, "profile", None)


def is_admin(user) -> bool:
    p = get_profile(user)
    return bool(
        getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
        or (p and getattr(p, "role", None) == "ADMIN")
    )


# =========================
# PERMISSÕES (LEGADO: macro strings)
# =========================
PERM_ORG = "org"
PERM_EDU = "educacao"
PERM_NEE = "nee"
PERM_ACCOUNTS = "accounts"
PERM_REPORTS = "reports"

ALL_PERMS = {PERM_ORG, PERM_EDU, PERM_NEE, PERM_ACCOUNTS, PERM_REPORTS}

ROLE_PERMS = {
    "ADMIN": ALL_PERMS,
    "MUNICIPAL": {PERM_ORG, PERM_EDU, PERM_NEE, PERM_REPORTS, PERM_ACCOUNTS},
    "SECRETARIA": {PERM_EDU, PERM_NEE, PERM_REPORTS, PERM_ACCOUNTS},
    "UNIDADE": {PERM_EDU, PERM_NEE, PERM_REPORTS, PERM_ACCOUNTS},
    "NEE": {PERM_NEE, PERM_REPORTS, PERM_ACCOUNTS},
    "LEITURA": {PERM_REPORTS, PERM_ACCOUNTS},
    "ALUNO": {PERM_ACCOUNTS},
}


# =========================
# PERMISSÕES (NOVO: granular / "definitivo")
# =========================
ROLE_PERMS_FINE = {
    "ADMIN": {
        "org.view",
        "org.manage_municipio",
        "org.manage_secretaria",
        "org.manage_unidade",
        "educacao.view",
        "educacao.manage",
        "nee.view",
        "nee.manage",
        "reports.view",
        "accounts.manage_users",
        "system.admin_django",
    },
    "MUNICIPAL": {
        "org.view",
        "org.manage_secretaria",
        "org.manage_unidade",
        "educacao.view",
        "educacao.manage",
        "nee.view",
        "nee.manage",
        "reports.view",
        "accounts.manage_users",
    },
    "SECRETARIA": {
        "org.view",
        "org.manage_unidade",
        "educacao.view",
        "educacao.manage",
        "nee.view",
        "nee.manage",
        "reports.view",
        "accounts.manage_users",
    },
    "UNIDADE": {
        "org.view",
        "educacao.view",
        "educacao.manage",
        "nee.view",
        "nee.manage",
        "reports.view",
        "accounts.manage_users",
    },
    "PROFESSOR": {
        "educacao.view",
    },
    "ALUNO": {
        
        
    },
    "VISUALIZACAO": {
        "org.view",
        "educacao.view",
        "nee.view",
        "reports.view",
    },
    "NEE": {"nee.view", "nee.manage", "reports.view", "accounts.manage_users"},
    "LEITURA": {"reports.view"},
}


def _macro_from_fine(perm: str) -> str | None:
    if not perm or "." not in perm:
        return None
    return perm.split(".", 1)[0]


def get_user_perms(user) -> set[str]:
    if not user or not getattr(user, "is_authenticated", False):
        return set()

    if is_admin(user):
        perms = set(ALL_PERMS)
        for fine in ROLE_PERMS_FINE.get("ADMIN", set()):
            perms.add(fine)
            m = _macro_from_fine(fine)
            if m:
                perms.add(m)
        return perms

    p = get_profile(user)
    if not p or not getattr(p, "ativo", True):
        return set()

    role = getattr(p, "role", None) or "LEITURA"

    perms = set(ROLE_PERMS.get(role, set()))
    fine_perms = set(ROLE_PERMS_FINE.get(role, set()))
    perms |= fine_perms

    for fp in fine_perms:
        m = _macro_from_fine(fp)
        if m:
            perms.add(m)

    return perms


def can(user, perm: str) -> bool:
    perms = get_user_perms(user)

    if perm in perms:
        return True

    if "." in perm:
        return False

    prefix = perm + "."
    return any(p.startswith(prefix) for p in perms)


# =========================
# SCOPES (filtros por município/unidade)
# =========================
def _require_auth_active(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    p = get_profile(user)
    if not p or not getattr(p, "ativo", True):
        return None
    return p


def scope_filter_municipios(user, qs):
    if not user or not getattr(user, "is_authenticated", False):
        return qs.none()
    if is_admin(user):
        return qs

    p = _require_auth_active(user)
    if not p:
        return qs.none()

    if getattr(p, "municipio_id", None):
        return qs.filter(id=p.municipio_id)

    return qs.none()


def scope_filter_secretarias(user, qs):
    if not user or not getattr(user, "is_authenticated", False):
        return qs.none()
    if is_admin(user):
        return qs

    p = _require_auth_active(user)
    if not p:
        return qs.none()

    role = getattr(p, "role", None)

    if role == "SECRETARIA" and getattr(p, "secretaria_id", None):
        return qs.filter(id=p.secretaria_id)

    if getattr(p, "municipio_id", None):
        return qs.filter(municipio_id=p.municipio_id)

    return qs.none()


def scope_filter_unidades(user, qs):
    if not user or not getattr(user, "is_authenticated", False):
        return qs.none()
    if is_admin(user):
        return qs

    p = _require_auth_active(user)
    if not p:
        return qs.none()

    role = getattr(p, "role", None)

    if role == "UNIDADE" and getattr(p, "unidade_id", None):
        return qs.filter(id=p.unidade_id)

    if role == "SECRETARIA" and getattr(p, "secretaria_id", None):
        return qs.filter(secretaria_id=p.secretaria_id)

    if getattr(p, "municipio_id", None):
        return qs.filter(secretaria__municipio_id=p.municipio_id)

    return qs.none()


def scope_filter_turmas(user, qs):
    """
    ✅ NOVO: PROFESSOR vê apenas as turmas em que está vinculado (Turma.professores)
    """
    if not user or not getattr(user, "is_authenticated", False):
        return qs.none()

    if is_admin(user):
        return qs

    p = _require_auth_active(user)
    if not p:
        return qs.none()

    role = getattr(p, "role", None)

    # ✅ PROFESSOR: apenas turmas vinculadas
    if role == "PROFESSOR":
        return qs.filter(professores=user).distinct()

    if role == "UNIDADE" and getattr(p, "unidade_id", None):
        return qs.filter(unidade_id=p.unidade_id)

    if getattr(p, "municipio_id", None):
        return qs.filter(unidade__secretaria__municipio_id=p.municipio_id)

    return qs.none()


def scope_filter_matriculas(user, qs):
    if not user or not getattr(user, "is_authenticated", False):
        return qs.none()

    if is_admin(user):
        return qs

    p = _require_auth_active(user)
    if not p:
        return qs.none()

    role = getattr(p, "role", None)

    # ✅ PROFESSOR: matrículas apenas das turmas dele
    if role == "PROFESSOR":
        return qs.filter(turma__professores=user).distinct()

    if role == "UNIDADE" and getattr(p, "unidade_id", None):
        return qs.filter(turma__unidade_id=p.unidade_id)

    if getattr(p, "municipio_id", None):
        return qs.filter(turma__unidade__secretaria__municipio_id=p.municipio_id)

    return qs.none()


def scope_filter_alunos(user, qs):
    """
    ✅ NOVO: PROFESSOR vê apenas alunos matriculados em turmas dele.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return qs.none()

    if is_admin(user):
        return qs

    p = _require_auth_active(user)
    if not p:
        return qs.none()

    from apps.educacao.models import Matricula  # evita import circular

    matriculas = Matricula.objects.filter(aluno_id=OuterRef("pk"))

    role = getattr(p, "role", None)

    # ✅ PROFESSOR: alunos com matrícula em turmas vinculadas ao professor
    if role == "PROFESSOR":
        matriculas = matriculas.filter(turma__professores=user)
        return qs.annotate(_has_scope=Exists(matriculas)).filter(_has_scope=True).distinct()

    # regra antiga
    if role == "UNIDADE" and getattr(p, "unidade_id", None):
        matriculas = matriculas.filter(turma__unidade_id=p.unidade_id)
    elif getattr(p, "municipio_id", None):
        matriculas = matriculas.filter(turma__unidade__secretaria__municipio_id=p.municipio_id)
    else:
        return qs.none()

    return qs.annotate(_has_scope=Exists(matriculas)).filter(_has_scope=True)
