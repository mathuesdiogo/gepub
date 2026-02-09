# apps/core/rbac.py
from __future__ import annotations

from django.db.models import Exists, OuterRef


# =========================
# PERFIL / ADMIN
# =========================
def get_profile(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    # mantém compatível com seu padrão atual
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

# Matriz simples por role (LEGADO - mantém)
ROLE_PERMS = {
    "ADMIN": ALL_PERMS,
    "MUNICIPAL": {PERM_ORG, PERM_EDU, PERM_NEE, PERM_REPORTS, PERM_ACCOUNTS},
    "SECRETARIA": {PERM_EDU, PERM_NEE, PERM_REPORTS, PERM_ACCOUNTS},
    "UNIDADE": {PERM_EDU, PERM_NEE, PERM_REPORTS, PERM_ACCOUNTS},
    "NEE": {PERM_NEE, PERM_REPORTS, PERM_ACCOUNTS},
    "LEITURA": {PERM_REPORTS, PERM_ACCOUNTS},
    "ALUNO": {PERM_ACCOUNTS},  # por enquanto só perfil/conta; depois evoluímos
}


# =========================
# PERMISSÕES (NOVO: granular / "definitivo")
# =========================
# Matriz inicial de perms finas (como combinamos no RBAC definitivo)
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
    },
    "UNIDADE": {
        "org.view",
        "educacao.view",
        "educacao.manage",
        "nee.view",
        "nee.manage",
        "reports.view",
    },
    "PROFESSOR": {
        "org.view",
        "educacao.view",
        "nee.view",
        "reports.view",
    },
    "ALUNO": {
        "educacao.view",
        "nee.view",
    },
    "VISUALIZACAO": {
        "org.view",
        "educacao.view",
        "nee.view",
        "reports.view",
    },
    # mantém compatibilidade com seus roles existentes:
    "NEE": {"nee.view", "nee.manage", "reports.view", "accounts.manage_users"},
    "LEITURA": {"reports.view"},
}


def _macro_from_fine(perm: str) -> str | None:
    """
    'educacao.manage' -> 'educacao'
    'org.view' -> 'org'
    """
    if not perm or "." not in perm:
        return None
    return perm.split(".", 1)[0]


def get_user_perms(user) -> set[str]:
    """
    Retorna um set de permissões do usuário.
    COMPATÍVEL:
      - inclui macros ('educacao') para não quebrar suas checagens atuais
      - inclui finas ('educacao.manage') para o RBAC definitivo
    """
    if not user or not getattr(user, "is_authenticated", False):
        return set()

    if is_admin(user):
        # admin recebe tudo (macros + finas)
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

    # legado
    perms = set(ROLE_PERMS.get(role, set()))

    # novo granular
    fine_perms = set(ROLE_PERMS_FINE.get(role, set()))
    perms |= fine_perms

    # garante que quem tem perm fina também “ganha” macro correspondente
    for fp in fine_perms:
        m = _macro_from_fine(fp)
        if m:
            perms.add(m)

    return perms


def can(user, perm: str) -> bool:
    """
    COMPATÍVEL com seu projeto:
      - se você passar 'educacao' continua funcionando
      - se você passar 'educacao.manage' também funciona
    Regras:
      - se tiver perm exata, ok
      - se for perm fina e usuário tiver macro correspondente, ok (opcional mas útil na migração)
    """
    perms = get_user_perms(user)
    if perm in perms:
        return True

    # fallback: 'educacao.manage' -> 'educacao'
    if "." in perm:
        macro = perm.split(".", 1)[0]
        return macro in perms

    return False


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
    """
    MUNICIPAL/SECRETARIA/UNIDADE/etc: enxerga só o município do profile.
    ADMIN: tudo.
    """
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
    """
    SECRETARIA: só sua secretaria (se tiver FK).
    Caso não tenha secretaria_id, cai para municipio_id.
    """
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
    """
    UNIDADE: só sua unidade (se tiver FK).
    SECRETARIA: unidades da secretaria (se tiver FK), senão por município.
    MUNICIPAL: unidades do município.
    """
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
        # assume Unidade tem FK secretaria (se não tiver, ajustamos depois)
        return qs.filter(secretaria_id=p.secretaria_id)

    if getattr(p, "municipio_id", None):
        # assume Unidade -> Secretaria -> Municipio como no seu scope atual
        return qs.filter(secretaria__municipio_id=p.municipio_id)

    return qs.none()


def scope_filter_turmas(user, qs):
    """
    qs: QuerySet de Turma
    (mantido do seu arquivo, sem mudar a lógica)
    """
    if not user or not getattr(user, "is_authenticated", False):
        return qs.none()

    if is_admin(user):
        return qs

    p = _require_auth_active(user)
    if not p:
        return qs.none()

    if getattr(p, "role", None) == "UNIDADE" and getattr(p, "unidade_id", None):
        return qs.filter(unidade_id=p.unidade_id)

    if getattr(p, "municipio_id", None):
        return qs.filter(unidade__secretaria__municipio_id=p.municipio_id)

    return qs.none()


def scope_filter_matriculas(user, qs):
    """
    qs: QuerySet de Matricula
    (mantido do seu arquivo, sem mudar a lógica)
    """
    if not user or not getattr(user, "is_authenticated", False):
        return qs.none()

    if is_admin(user):
        return qs

    p = _require_auth_active(user)
    if not p:
        return qs.none()

    if getattr(p, "role", None) == "UNIDADE" and getattr(p, "unidade_id", None):
        return qs.filter(turma__unidade_id=p.unidade_id)

    if getattr(p, "municipio_id", None):
        return qs.filter(turma__unidade__secretaria__municipio_id=p.municipio_id)

    return qs.none()


def scope_filter_alunos(user, qs):
    """
    qs: QuerySet de Aluno
    Como Aluno não tem FK direta para unidade/município, filtramos por existência de matrícula.
    Obs.: alunos sem matrícula só aparecem para ADMIN.
    (mantido do seu arquivo, só deixei o helper de profile/ativo)
    """
    if not user or not getattr(user, "is_authenticated", False):
        return qs.none()

    if is_admin(user):
        return qs

    p = _require_auth_active(user)
    if not p:
        return qs.none()

    from educacao.models import Matricula  # evita import circular

    matriculas = Matricula.objects.filter(aluno_id=OuterRef("pk"))

    if getattr(p, "role", None) == "UNIDADE" and getattr(p, "unidade_id", None):
        matriculas = matriculas.filter(turma__unidade_id=p.unidade_id)
    elif getattr(p, "municipio_id", None):
        matriculas = matriculas.filter(turma__unidade__secretaria__municipio_id=p.municipio_id)
    else:
        return qs.none()

    return qs.annotate(_has_scope=Exists(matriculas)).filter(_has_scope=True)
