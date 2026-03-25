# apps/core/rbac.py
from __future__ import annotations

from django.db.models import Exists, OuterRef


# =========================
# PERFIL / ADMIN
# =========================
def normalize_role(role: str | None) -> str:
    return ((role or "") + "").strip().upper() or "LEITURA"


def get_profile(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    return getattr(user, "profile", None)


def is_admin(user) -> bool:
    p = get_profile(user)
    role = normalize_role(getattr(p, "role", None) if p else None)
    return bool(
        getattr(user, "is_superuser", False)
        or role == "ADMIN"
    )


# =========================
# PAPÉIS (famílias / escopo / gestão)
# =========================
ROLE_SCOPE_BASE: dict[str, str] = {
    # Canon
    "ADMIN": "ADMIN",
    "MUNICIPAL": "MUNICIPAL",
    "SECRETARIA": "SECRETARIA",
    "UNIDADE": "UNIDADE",
    "PROFESSOR": "PROFESSOR",
    "ALUNO": "ALUNO",
    "NEE": "NEE",
    "LEITURA": "LEITURA",
    "VISUALIZACAO": "LEITURA",
    # Governança
    "AUDITORIA": "MUNICIPAL",
    "RH_GESTOR": "MUNICIPAL",
    "PROTOCOLO": "SECRETARIA",
    "CAD_GESTOR": "MUNICIPAL",
    "CAD_OPER": "SECRETARIA",
    # Saúde
    "SAU_SECRETARIO": "SECRETARIA",
    "SAU_DIRETOR": "UNIDADE",
    "SAU_COORD": "UNIDADE",
    "SAU_MEDICO": "UNIDADE",
    "SAU_ENFERMEIRO": "UNIDADE",
    "SAU_TEC_ENF": "UNIDADE",
    "SAU_ACS": "UNIDADE",
    "SAU_RECEPCAO": "UNIDADE",
    "SAU_REGULACAO": "UNIDADE",
    "SAU_FARMACIA": "UNIDADE",
    # Educação
    "EDU_SECRETARIO": "SECRETARIA",
    "EDU_DIRETOR": "UNIDADE",
    "EDU_COORD": "UNIDADE",
    "EDU_PROF": "PROFESSOR",
    "EDU_SECRETARIA": "UNIDADE",
    "EDU_TRANSPORTE": "UNIDADE",
    # NEE
    "NEE_COORD_MUN": "MUNICIPAL",
    "NEE_COORD_ESC": "UNIDADE",
    "NEE_MEDIADOR": "UNIDADE",
    "NEE_TECNICO": "UNIDADE",
    # Dados / BI
    "DADOS_GESTOR": "MUNICIPAL",
    "DADOS_ANALISTA": "SECRETARIA",
    # Integrações
    "INT_TI": "MUNICIPAL",
    "INT_GESTAO": "MUNICIPAL",
    "INT_LEITOR": "MUNICIPAL",
    # Portal
    "PORTAL_ADMIN": "MUNICIPAL",
    "PORTAL_EDITOR": "SECRETARIA",
    "PORTAL_APROV": "SECRETARIA",
    "PORTAL_DESIGN": "SECRETARIA",
    # Câmara
    "CAMARA_ADMIN": "MUNICIPAL",
    "CAMARA_SECRETARIA": "SECRETARIA",
    "CAMARA_COMUNICACAO": "SECRETARIA",
    "CAMARA_TRANSPARENCIA": "SECRETARIA",
    "CAMARA_VEREADOR": "MUNICIPAL",
    "CAMARA_AUDITOR": "MUNICIPAL",
    # Portal cidadão
    "CIDADAO": "ALUNO",
}

# Fallback de permissões para papéis legados/não mapeados explicitamente.
ROLE_PERM_FALLBACK: dict[str, str] = {
    "VISUALIZACAO": "LEITURA",
}

UNIT_OPERATIONAL_ROLES: set[str] = {
    "PROFESSOR",
    "EDU_PROF",
    "ALUNO",
    "CIDADAO",
    "NEE",
    "NEE_MEDIADOR",
    "NEE_TECNICO",
    "NEE_COORD_ESC",
    "LEITURA",
    "SAU_MEDICO",
    "SAU_ENFERMEIRO",
    "SAU_TEC_ENF",
    "SAU_ACS",
    "SAU_RECEPCAO",
    "SAU_REGULACAO",
    "SAU_FARMACIA",
    "EDU_SECRETARIA",
    "EDU_TRANSPORTE",
}

UNIDADE_MANAGER_ROLES: set[str] = {
    "UNIDADE",
    "EDU_DIRETOR",
    "EDU_COORD",
    "SAU_DIRETOR",
    "SAU_COORD",
}

SECRETARIA_MANAGER_ROLES: set[str] = {
    "SECRETARIA",
    "SAU_SECRETARIO",
    "EDU_SECRETARIO",
    "PROTOCOLO",
    "CAD_OPER",
    "PORTAL_EDITOR",
    "PORTAL_APROV",
    "PORTAL_DESIGN",
    "CAMARA_SECRETARIA",
    "CAMARA_COMUNICACAO",
    "CAMARA_TRANSPARENCIA",
    "DADOS_ANALISTA",
}

MUNICIPAL_SPECIALIST_ROLES: set[str] = {
    "AUDITORIA",
    "RH_GESTOR",
    "CAD_GESTOR",
    "NEE_COORD_MUN",
    "DADOS_GESTOR",
    "DADOS_ANALISTA",
    "INT_TI",
    "INT_GESTAO",
    "INT_LEITOR",
    "PORTAL_ADMIN",
    "CAMARA_ADMIN",
    "CAMARA_VEREADOR",
    "CAMARA_AUDITOR",
}

# Manager role -> papéis atribuíveis.
ROLE_MANAGEMENT_ALLOWED: dict[str, set[str]] = {
    "ADMIN": set(ROLE_SCOPE_BASE.keys()),
    "MUNICIPAL": (
        UNIT_OPERATIONAL_ROLES
        | UNIDADE_MANAGER_ROLES
        | SECRETARIA_MANAGER_ROLES
        | MUNICIPAL_SPECIALIST_ROLES
    ),
    "SECRETARIA": UNIT_OPERATIONAL_ROLES | UNIDADE_MANAGER_ROLES | {"CAD_OPER", "PROTOCOLO"},
    "UNIDADE": UNIT_OPERATIONAL_ROLES,
}


def role_scope_base(role: str | None) -> str:
    return ROLE_SCOPE_BASE.get(normalize_role(role), "LEITURA")


def user_role_scope_base(user) -> str:
    p = get_profile(user)
    return role_scope_base(getattr(p, "role", None) if p else None)


def is_professor_profile_role(role: str | None) -> bool:
    return role_scope_base(role) == "PROFESSOR"


def allowed_roles_for_manager_role(manager_role: str | None) -> set[str]:
    return set(ROLE_MANAGEMENT_ALLOWED.get(normalize_role(manager_role), set()))


# =========================
# PERMISSÕES (LEGADO: macro strings)
# =========================
PERM_ORG = "org"
PERM_EDU = "educacao"
PERM_AVALIACOES = "avaliacoes"
PERM_NEE = "nee"
PERM_SAUDE = "saude"
PERM_BILLING = "billing"
PERM_FINANCEIRO = "financeiro"
PERM_ACCOUNTS = "accounts"
PERM_REPORTS = "reports"
PERM_PROCESSOS = "processos"
PERM_COMPRAS = "compras"
PERM_CONTRATOS = "contratos"
PERM_INTEGRACOES = "integracoes"
PERM_COMUNICACAO = "comunicacao"
PERM_PAINEIS = "paineis"
PERM_CONVERSOR = "conversor"
PERM_RH = "rh"
PERM_PONTO = "ponto"
PERM_FOLHA = "folha"
PERM_PATRIMONIO = "patrimonio"
PERM_ALMOXARIFADO = "almoxarifado"
PERM_FROTA = "frota"
PERM_OUVIDORIA = "ouvidoria"
PERM_TRIBUTOS = "tributos"
PERM_CAMARA = "camara"

ALL_PERMS = {
    PERM_ORG,
    PERM_EDU,
    PERM_AVALIACOES,
    PERM_NEE,
    PERM_SAUDE,
    PERM_BILLING,
    PERM_FINANCEIRO,
    PERM_ACCOUNTS,
    PERM_REPORTS,
    PERM_PROCESSOS,
    PERM_COMPRAS,
    PERM_CONTRATOS,
    PERM_INTEGRACOES,
    PERM_COMUNICACAO,
    PERM_PAINEIS,
    PERM_CONVERSOR,
    PERM_RH,
    PERM_PONTO,
    PERM_FOLHA,
    PERM_PATRIMONIO,
    PERM_ALMOXARIFADO,
    PERM_FROTA,
    PERM_OUVIDORIA,
    PERM_TRIBUTOS,
    PERM_CAMARA,
}

ROLE_PERMS = {
    "ADMIN": ALL_PERMS,
    "MUNICIPAL": {
        PERM_ORG,
        PERM_EDU,
        PERM_AVALIACOES,
        PERM_NEE,
        PERM_SAUDE,
        PERM_BILLING,
        PERM_FINANCEIRO,
        PERM_REPORTS,
        PERM_ACCOUNTS,
        PERM_PROCESSOS,
        PERM_COMPRAS,
        PERM_CONTRATOS,
        PERM_INTEGRACOES,
        PERM_COMUNICACAO,
        PERM_PAINEIS,
        PERM_CONVERSOR,
        PERM_RH,
        PERM_PONTO,
        PERM_FOLHA,
        PERM_PATRIMONIO,
        PERM_ALMOXARIFADO,
        PERM_FROTA,
        PERM_OUVIDORIA,
        PERM_TRIBUTOS,
        PERM_CAMARA,
    },
    "SECRETARIA": {
        PERM_EDU,
        PERM_AVALIACOES,
        PERM_NEE,
        PERM_SAUDE,
        PERM_FINANCEIRO,
        PERM_REPORTS,
        PERM_ACCOUNTS,
        PERM_PROCESSOS,
        PERM_COMPRAS,
        PERM_CONTRATOS,
        PERM_INTEGRACOES,
        PERM_COMUNICACAO,
        PERM_PAINEIS,
        PERM_CONVERSOR,
        PERM_RH,
        PERM_PONTO,
        PERM_FOLHA,
        PERM_PATRIMONIO,
        PERM_ALMOXARIFADO,
        PERM_FROTA,
        PERM_OUVIDORIA,
        PERM_TRIBUTOS,
        PERM_CAMARA,
    },
    "UNIDADE": {
        PERM_EDU,
        PERM_AVALIACOES,
        PERM_NEE,
        PERM_SAUDE,
        PERM_FINANCEIRO,
        PERM_REPORTS,
        PERM_ACCOUNTS,
        PERM_PROCESSOS,
        PERM_COMPRAS,
        PERM_CONTRATOS,
        PERM_INTEGRACOES,
        PERM_COMUNICACAO,
        PERM_PAINEIS,
        PERM_CONVERSOR,
        PERM_RH,
        PERM_PONTO,
        PERM_FOLHA,
        PERM_PATRIMONIO,
        PERM_ALMOXARIFADO,
        PERM_FROTA,
        PERM_OUVIDORIA,
        PERM_TRIBUTOS,
        PERM_CAMARA,
    },
    "NEE": {PERM_NEE, PERM_SAUDE, PERM_FINANCEIRO, PERM_REPORTS, PERM_ACCOUNTS, PERM_PROCESSOS, PERM_PAINEIS},
    "LEITURA": {
        PERM_FINANCEIRO,
        PERM_REPORTS,
        PERM_ACCOUNTS,
        PERM_PROCESSOS,
        PERM_COMPRAS,
        PERM_CONTRATOS,
        PERM_COMUNICACAO,
        PERM_PAINEIS,
        PERM_CONVERSOR,
        PERM_CAMARA,
    },
    "ALUNO": {PERM_ACCOUNTS},
}


# =========================
# PERMISSÕES (granular)
# =========================
ROLE_PERMS_FINE = {
    "ADMIN": {
        "org.view",
        "org.manage_municipio",
        "org.manage_secretaria",
        "org.manage_unidade",
        "educacao.view",
        "educacao.manage",
        "avaliacoes.view",
        "avaliacoes.manage",
        "nee.view",
        "nee.manage",
        "reports.view",
        "accounts.manage_users",
        "system.admin_django",
        "saude.view",
        "saude.manage",
        "billing.view",
        "billing.manage",
        "billing.admin",
        "financeiro.view",
        "financeiro.manage",
        "financeiro.contabilidade",
        "financeiro.tesouraria",
        "processos.view",
        "processos.manage",
        "compras.view",
        "compras.manage",
        "contratos.view",
        "contratos.manage",
        "integracoes.view",
        "integracoes.manage",
        "integracoes.admin",
        "comunicacao.view",
        "comunicacao.manage",
        "comunicacao.send",
        "comunicacao.audit",
        "comunicacao.admin",
        "paineis.view",
        "paineis.manage",
        "paineis.publish",
        "conversor.view",
        "conversor.manage",
        "rh.view",
        "rh.manage",
        "ponto.view",
        "ponto.manage",
        "folha.view",
        "folha.manage",
        "patrimonio.view",
        "patrimonio.manage",
        "almoxarifado.view",
        "almoxarifado.manage",
        "frota.view",
        "frota.manage",
        "ouvidoria.view",
        "ouvidoria.manage",
        "tributos.view",
        "tributos.manage",
        "camara.view",
        "camara.manage",
        "camara.sessoes.manage",
        "camara.proposicoes.manage",
        "camara.cms.manage",
        "camara.transparencia.manage",
        "camara.transmissoes.manage",
    },
    "MUNICIPAL": {
        "org.view",
        "org.manage_secretaria",
        "org.manage_unidade",
        "educacao.view",
        "educacao.manage",
        "avaliacoes.view",
        "avaliacoes.manage",
        "nee.view",
        "nee.manage",
        "reports.view",
        "accounts.manage_users",
        "saude.view",
        "saude.manage",
        "billing.view",
        "billing.manage",
        "financeiro.view",
        "financeiro.manage",
        "financeiro.contabilidade",
        "financeiro.tesouraria",
        "processos.view",
        "processos.manage",
        "compras.view",
        "compras.manage",
        "contratos.view",
        "contratos.manage",
        "integracoes.view",
        "integracoes.manage",
        "integracoes.admin",
        "comunicacao.view",
        "comunicacao.manage",
        "comunicacao.send",
        "comunicacao.audit",
        "comunicacao.admin",
        "paineis.view",
        "paineis.manage",
        "paineis.publish",
        "conversor.view",
        "conversor.manage",
        "rh.view",
        "rh.manage",
        "ponto.view",
        "ponto.manage",
        "folha.view",
        "folha.manage",
        "patrimonio.view",
        "patrimonio.manage",
        "almoxarifado.view",
        "almoxarifado.manage",
        "frota.view",
        "frota.manage",
        "ouvidoria.view",
        "ouvidoria.manage",
        "tributos.view",
        "tributos.manage",
        "camara.view",
        "camara.manage",
        "camara.sessoes.manage",
        "camara.proposicoes.manage",
        "camara.cms.manage",
        "camara.transparencia.manage",
        "camara.transmissoes.manage",
    },
    "SECRETARIA": {
        "org.view",
        "org.manage_unidade",
        "educacao.view",
        "educacao.manage",
        "avaliacoes.view",
        "avaliacoes.manage",
        "nee.view",
        "nee.manage",
        "saude.view",
        "saude.manage",
        "reports.view",
        "accounts.manage_users",
        "financeiro.view",
        "processos.view",
        "processos.manage",
        "compras.view",
        "compras.manage",
        "contratos.view",
        "contratos.manage",
        "integracoes.view",
        "integracoes.manage",
        "comunicacao.view",
        "comunicacao.manage",
        "comunicacao.send",
        "comunicacao.audit",
        "paineis.view",
        "paineis.manage",
        "paineis.publish",
        "conversor.view",
        "conversor.manage",
        "rh.view",
        "rh.manage",
        "ponto.view",
        "ponto.manage",
        "folha.view",
        "folha.manage",
        "patrimonio.view",
        "almoxarifado.view",
        "frota.view",
        "ouvidoria.view",
        "ouvidoria.manage",
        "tributos.view",
        "camara.view",
        "camara.cms.manage",
    },
    "UNIDADE": {
        "org.view",
        "educacao.view",
        "educacao.manage",
        "avaliacoes.view",
        "avaliacoes.manage",
        "nee.view",
        "nee.manage",
        "saude.view",
        "reports.view",
        "accounts.manage_users",
        "financeiro.view",
        "processos.view",
        "compras.view",
        "contratos.view",
        "integracoes.view",
        "comunicacao.view",
        "comunicacao.send",
        "paineis.view",
        "conversor.view",
        "rh.view",
        "ponto.view",
        "folha.view",
        "patrimonio.view",
        "almoxarifado.view",
        "frota.view",
        "ouvidoria.view",
        "tributos.view",
        "camara.view",
    },
    "PROFESSOR": {
        "educacao.view",
        "avaliacoes.view",
        "avaliacoes.manage",
    },
    "ALUNO": set(),
    "NEE": {
        "nee.view",
        "nee.manage",
        "reports.view",
        "accounts.manage_users",
        "financeiro.view",
        "processos.view",
        "paineis.view",
    },
    "LEITURA": {
        "reports.view",
        "financeiro.view",
        "processos.view",
        "compras.view",
        "contratos.view",
        "paineis.view",
        "conversor.view",
        "camara.view",
    },
    # Perfis profissionais (GEPUB)
    "AUDITORIA": {
        "org.view",
        "educacao.view",
        "avaliacoes.view",
        "nee.view",
        "saude.view",
        "financeiro.view",
        "processos.view",
        "compras.view",
        "contratos.view",
        "integracoes.view",
        "comunicacao.view",
        "comunicacao.audit",
        "camara.view",
        "reports.view",
        "paineis.view",
        "conversor.view",
        "rh.view",
        "ponto.view",
        "folha.view",
        "patrimonio.view",
        "almoxarifado.view",
        "frota.view",
        "ouvidoria.view",
        "tributos.view",
    },
    "RH_GESTOR": {
        "org.view",
        "rh.view",
        "rh.manage",
        "ponto.view",
        "ponto.manage",
        "folha.view",
        "folha.manage",
        "reports.view",
    },
    "PROTOCOLO": {
        "processos.view",
        "processos.manage",
        "ouvidoria.view",
        "ouvidoria.manage",
        "comunicacao.view",
        "comunicacao.send",
    },
    "CAD_GESTOR": {
        "org.view",
        "org.manage_secretaria",
        "org.manage_unidade",
        "accounts.manage_users",
    },
    "CAD_OPER": {
        "org.view",
    },
    "SAU_SECRETARIO": {
        "saude.view",
        "saude.manage",
        "reports.view",
        "paineis.view",
        "comunicacao.view",
        "comunicacao.send",
    },
    "SAU_DIRETOR": {"saude.view", "saude.manage", "reports.view", "comunicacao.view", "comunicacao.send"},
    "SAU_COORD": {"saude.view", "saude.manage", "comunicacao.view", "comunicacao.send"},
    "SAU_MEDICO": {"saude.view", "saude.manage"},
    "SAU_ENFERMEIRO": {"saude.view", "saude.manage"},
    "SAU_TEC_ENF": {"saude.view"},
    "SAU_ACS": {"saude.view"},
    "SAU_RECEPCAO": {"saude.view"},
    "SAU_REGULACAO": {"saude.view", "saude.manage"},
    "SAU_FARMACIA": {"saude.view"},
    "EDU_SECRETARIO": {
        "org.view",
        "educacao.view",
        "educacao.manage",
        "avaliacoes.view",
        "nee.view",
        "reports.view",
        "paineis.view",
        "comunicacao.view",
        "comunicacao.send",
    },
    "EDU_DIRETOR": {
        "educacao.view",
        "educacao.manage",
        "avaliacoes.view",
        "avaliacoes.manage",
        "nee.view",
        "comunicacao.view",
        "comunicacao.send",
    },
    "EDU_COORD": {
        "educacao.view",
        "educacao.manage",
        "avaliacoes.view",
        "avaliacoes.manage",
        "nee.view",
        "comunicacao.view",
        "comunicacao.send",
    },
    "EDU_PROF": {
        "educacao.view",
        "avaliacoes.view",
        "avaliacoes.manage",
    },
    "EDU_SECRETARIA": {"educacao.view", "educacao.manage", "comunicacao.view"},
    "EDU_TRANSPORTE": {"educacao.view"},
    "NEE_COORD_MUN": {
        "nee.view",
        "nee.manage",
        "educacao.view",
        "saude.view",
        "reports.view",
    },
    "NEE_COORD_ESC": {"nee.view", "nee.manage", "educacao.view"},
    "NEE_MEDIADOR": {"nee.view", "nee.manage", "educacao.view"},
    "NEE_TECNICO": {"nee.view", "nee.manage", "educacao.view", "saude.view"},
    "DADOS_GESTOR": {
        "reports.view",
        "paineis.view",
        "paineis.manage",
        "paineis.publish",
        "conversor.view",
        "conversor.manage",
        "comunicacao.view",
        "comunicacao.audit",
    },
    "DADOS_ANALISTA": {
        "reports.view",
        "paineis.view",
        "conversor.view",
        "comunicacao.view",
        "comunicacao.audit",
    },
    "INT_TI": {
        "integracoes.view",
        "integracoes.manage",
        "integracoes.admin",
        "reports.view",
    },
    "INT_GESTAO": {
        "integracoes.view",
        "integracoes.manage",
        "reports.view",
    },
    "INT_LEITOR": {
        "integracoes.view",
        "reports.view",
    },
    "PORTAL_ADMIN": {"org.view"},
    "PORTAL_EDITOR": {"org.view", "comunicacao.view", "comunicacao.send"},
    "PORTAL_APROV": {"org.view", "comunicacao.view", "comunicacao.audit"},
    "PORTAL_DESIGN": {"org.view"},
    "CAMARA_ADMIN": {
        "camara.view",
        "camara.manage",
        "camara.sessoes.manage",
        "camara.proposicoes.manage",
        "camara.cms.manage",
        "camara.transparencia.manage",
        "camara.transmissoes.manage",
    },
    "CAMARA_SECRETARIA": {
        "camara.view",
        "camara.sessoes.manage",
        "camara.proposicoes.manage",
    },
    "CAMARA_COMUNICACAO": {
        "camara.view",
        "camara.cms.manage",
        "camara.transmissoes.manage",
    },
    "CAMARA_TRANSPARENCIA": {
        "camara.view",
        "camara.transparencia.manage",
    },
    "CAMARA_VEREADOR": {
        "camara.view",
        "camara.proposicoes.manage",
    },
    "CAMARA_AUDITOR": {
        "camara.view",
    },
    "CIDADAO": set(),
}


def _macro_from_fine(perm: str) -> str | None:
    if not perm or "." not in perm:
        return None
    return perm.split(".", 1)[0]


def _resolve_perm_role(role: str) -> str:
    if role in ROLE_PERMS or role in ROLE_PERMS_FINE:
        return role
    return ROLE_PERM_FALLBACK.get(role, "LEITURA")


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

    role = normalize_role(getattr(p, "role", None))
    perm_role = _resolve_perm_role(role)

    perms = set(ROLE_PERMS.get(perm_role, set()))

    fine_perms = set(ROLE_PERMS_FINE.get(perm_role, set()))
    if role != perm_role:
        fine_perms |= set(ROLE_PERMS_FINE.get(role, set()))

    perms |= fine_perms

    for fp in fine_perms:
        m = _macro_from_fine(fp)
        if m:
            perms.add(m)

    return perms


def can(user, perm: str) -> bool:
    # Regras sensíveis: gestão comercial de planos GEPUB é exclusiva do admin global.
    if perm == "billing.admin":
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_superuser", False):
            return True
        profile = get_profile(user)
        role = normalize_role(getattr(profile, "role", None) if profile else None)
        return role == "ADMIN"

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


def _resolve_secretaria_id_from_profile(profile) -> int | None:
    secretaria_id = getattr(profile, "secretaria_id", None)
    if secretaria_id:
        return int(secretaria_id)

    unidade_id = getattr(profile, "unidade_id", None)
    if not unidade_id:
        return None

    try:
        from apps.org.models import Unidade

        return Unidade.objects.filter(pk=unidade_id).values_list("secretaria_id", flat=True).first()
    except Exception:
        return None


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

    base = role_scope_base(getattr(p, "role", None))

    if base in {"SECRETARIA", "UNIDADE"}:
        secretaria_id = _resolve_secretaria_id_from_profile(p)
        if secretaria_id:
            return qs.filter(id=secretaria_id)
        return qs.none()

    if base == "ALUNO":
        return qs.none()

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

    base = role_scope_base(getattr(p, "role", None))

    if base == "UNIDADE" and getattr(p, "unidade_id", None):
        return qs.filter(id=p.unidade_id)

    if base == "SECRETARIA":
        secretaria_id = _resolve_secretaria_id_from_profile(p)
        if secretaria_id:
            return qs.filter(secretaria_id=secretaria_id)
        return qs.none()

    if base == "ALUNO":
        return qs.none()

    if getattr(p, "municipio_id", None):
        return qs.filter(secretaria__municipio_id=p.municipio_id)

    return qs.none()


def _collect_local_estrutural_descendants_ids(local_id: int) -> set[int]:
    try:
        from apps.org.models import LocalEstrutural
    except Exception:
        return {int(local_id)}

    visited: set[int] = {int(local_id)}
    frontier: set[int] = {int(local_id)}
    while frontier:
        child_ids = set(
            LocalEstrutural.objects.filter(local_pai_id__in=frontier).values_list("id", flat=True)
        )
        child_ids -= visited
        if not child_ids:
            break
        visited |= child_ids
        frontier = child_ids
    return visited


def scope_filter_locais_estruturais(user, qs):
    if not user or not getattr(user, "is_authenticated", False):
        return qs.none()
    if is_admin(user):
        return qs

    p = _require_auth_active(user)
    if not p:
        return qs.none()

    base = role_scope_base(getattr(p, "role", None))

    if getattr(p, "local_estrutural_id", None):
        local_ids = _collect_local_estrutural_descendants_ids(int(p.local_estrutural_id))
        return qs.filter(id__in=local_ids)

    if base == "UNIDADE" and getattr(p, "unidade_id", None):
        return qs.filter(unidade_id=p.unidade_id)

    if base == "SECRETARIA":
        secretaria_id = _resolve_secretaria_id_from_profile(p)
        if secretaria_id:
            return qs.filter(secretaria_id=secretaria_id)
        return qs.none()

    if base == "ALUNO":
        return qs.none()

    if getattr(p, "municipio_id", None):
        return qs.filter(municipio_id=p.municipio_id)

    return qs.none()


def scope_filter_turmas(user, qs):
    """
    Professor (inclui perfis docentes) vê apenas as turmas em que está vinculado.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return qs.none()

    if is_admin(user):
        return qs

    p = _require_auth_active(user)
    if not p:
        return qs.none()

    base = role_scope_base(getattr(p, "role", None))

    if base == "PROFESSOR":
        return qs.filter(professores=user).distinct()

    if base == "UNIDADE" and getattr(p, "unidade_id", None):
        return qs.filter(unidade_id=p.unidade_id)

    if base == "SECRETARIA":
        secretaria_id = _resolve_secretaria_id_from_profile(p)
        if secretaria_id:
            return qs.filter(unidade__secretaria_id=secretaria_id)
        return qs.none()

    if base == "ALUNO":
        return qs.none()

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

    base = role_scope_base(getattr(p, "role", None))

    if base == "PROFESSOR":
        return qs.filter(turma__professores=user).distinct()

    if base == "UNIDADE" and getattr(p, "unidade_id", None):
        return qs.filter(turma__unidade_id=p.unidade_id)

    if base == "SECRETARIA":
        secretaria_id = _resolve_secretaria_id_from_profile(p)
        if secretaria_id:
            return qs.filter(turma__unidade__secretaria_id=secretaria_id)
        return qs.none()

    if base == "ALUNO":
        if getattr(p, "aluno_id", None):
            return qs.filter(aluno_id=p.aluno_id)
        return qs.none()

    if getattr(p, "municipio_id", None):
        return qs.filter(turma__unidade__secretaria__municipio_id=p.municipio_id)

    return qs.none()


def scope_filter_alunos(user, qs):
    """
    Professor (inclui perfis docentes) vê apenas alunos matriculados em turmas dele.
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
    base = role_scope_base(getattr(p, "role", None))

    if base == "PROFESSOR":
        matriculas = matriculas.filter(turma__professores=user)
        return qs.annotate(_has_scope=Exists(matriculas)).filter(_has_scope=True).distinct()

    if base == "UNIDADE" and getattr(p, "unidade_id", None):
        matriculas = matriculas.filter(turma__unidade_id=p.unidade_id)
    elif base == "SECRETARIA":
        secretaria_id = _resolve_secretaria_id_from_profile(p)
        if secretaria_id:
            matriculas = matriculas.filter(turma__unidade__secretaria_id=secretaria_id)
        else:
            return qs.none()
    elif base == "ALUNO":
        if getattr(p, "aluno_id", None):
            return qs.filter(pk=p.aluno_id)
        return qs.none()
    elif getattr(p, "municipio_id", None):
        matriculas = matriculas.filter(turma__unidade__secretaria__municipio_id=p.municipio_id)
    else:
        return qs.none()

    return qs.annotate(_has_scope=Exists(matriculas)).filter(_has_scope=True)
