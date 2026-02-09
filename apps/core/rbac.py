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
    return bool(getattr(user, "is_superuser", False) or getattr(user, "is_staff", False) or (p and p.role == "ADMIN"))


# =========================
# PERMISSÕES (strings)
# =========================
PERM_ORG = "org"
PERM_EDU = "educacao"
PERM_NEE = "nee"
PERM_ACCOUNTS = "accounts"
PERM_REPORTS = "reports"

ALL_PERMS = {PERM_ORG, PERM_EDU, PERM_NEE, PERM_ACCOUNTS, PERM_REPORTS}

# Matriz simples por role (ajuste depois com granularidade fina)
ROLE_PERMS = {
    "ADMIN": ALL_PERMS,
    "MUNICIPAL": {PERM_ORG, PERM_EDU, PERM_NEE, PERM_REPORTS, PERM_ACCOUNTS},
    "SECRETARIA": {PERM_EDU, PERM_NEE, PERM_REPORTS, PERM_ACCOUNTS},
    "UNIDADE": {PERM_EDU, PERM_NEE, PERM_REPORTS, PERM_ACCOUNTS},
    "NEE": {PERM_NEE, PERM_REPORTS, PERM_ACCOUNTS},
    "LEITURA": {PERM_REPORTS, PERM_ACCOUNTS},
    "ALUNO": {PERM_ACCOUNTS},  # por enquanto só perfil/conta; depois evoluímos
}


def get_user_perms(user) -> set[str]:
    """
    Retorna um set de permissões (strings) que o usuário tem.
    Admin vê tudo.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return set()

    if is_admin(user):
        return set(ALL_PERMS)

    p = get_profile(user)
    if not p or not getattr(p, "ativo", True):
        return set()

    return set(ROLE_PERMS.get(p.role, set()))


def can(user, perm: str) -> bool:
    """
    Checa se o usuário tem uma permissão macro (org/educacao/nee/accounts/reports).
    """
    return perm in get_user_perms(user)


# =========================
# SCOPES (filtros por município/unidade)
# =========================
def scope_filter_turmas(user, qs):
    """
    qs: QuerySet de Turma
    """
    if not user or not getattr(user, "is_authenticated", False):
        return qs.none()

    if is_admin(user):
        return qs

    p = get_profile(user)
    if not p or not getattr(p, "ativo", True):
        return qs.none()

    if p.role == "UNIDADE" and p.unidade_id:
        return qs.filter(unidade_id=p.unidade_id)

    if p.municipio_id:
        return qs.filter(unidade__secretaria__municipio_id=p.municipio_id)

    return qs.none()


def scope_filter_matriculas(user, qs):
    """
    qs: QuerySet de Matricula
    """
    if not user or not getattr(user, "is_authenticated", False):
        return qs.none()

    if is_admin(user):
        return qs

    p = get_profile(user)
    if not p or not getattr(p, "ativo", True):
        return qs.none()

    if p.role == "UNIDADE" and p.unidade_id:
        return qs.filter(turma__unidade_id=p.unidade_id)

    if p.municipio_id:
        return qs.filter(turma__unidade__secretaria__municipio_id=p.municipio_id)

    return qs.none()


def scope_filter_alunos(user, qs):
    """
    qs: QuerySet de Aluno
    Como Aluno não tem FK direta para unidade/município, filtramos por existência de matrícula.
    Obs.: alunos sem matrícula só aparecem para ADMIN.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return qs.none()

    if is_admin(user):
        return qs

    p = get_profile(user)
    if not p or not getattr(p, "ativo", True):
        return qs.none()

    from educacao.models import Matricula  # evita import circular

    matriculas = Matricula.objects.filter(aluno_id=OuterRef("pk"))

    if p.role == "UNIDADE" and p.unidade_id:
        matriculas = matriculas.filter(turma__unidade_id=p.unidade_id)
    elif p.municipio_id:
        matriculas = matriculas.filter(turma__unidade__secretaria__municipio_id=p.municipio_id)
    else:
        return qs.none()

    return qs.annotate(_has_scope=Exists(matriculas)).filter(_has_scope=True)
