# apps/core/context_processors.py
from __future__ import annotations

from apps.core.module_access import module_enabled_for_user
from apps.core.rbac import can


def permissions(request):
    """Permissões usadas nos templates (menu/sidebar).

    Mantém as chaves esperadas pelo seu base.html e telas de Educação.
    """
    u = getattr(request, "user", None)
    role = (getattr(getattr(u, "profile", None), "role", "") or "").upper()
    is_professor_role = role == "PROFESSOR"
    can_publicacoes_admin = role in {"ADMIN", "MUNICIPAL", "SECRETARIA"} or bool(getattr(u, "is_superuser", False))
    edu_enabled = module_enabled_for_user(u, "educacao")
    avaliacoes_enabled = module_enabled_for_user(u, "avaliacoes")
    nee_enabled = module_enabled_for_user(u, "nee")
    saude_enabled = module_enabled_for_user(u, "saude")
    financeiro_enabled = module_enabled_for_user(u, "financeiro")
    processos_enabled = module_enabled_for_user(u, "processos")
    compras_enabled = module_enabled_for_user(u, "compras")
    contratos_enabled = module_enabled_for_user(u, "contratos")
    integracoes_enabled = module_enabled_for_user(u, "integracoes")
    paineis_enabled = module_enabled_for_user(u, "paineis")
    conversor_enabled = module_enabled_for_user(u, "conversor")
    rh_enabled = module_enabled_for_user(u, "rh")
    ponto_enabled = module_enabled_for_user(u, "ponto")
    folha_enabled = module_enabled_for_user(u, "folha")
    patrimonio_enabled = module_enabled_for_user(u, "patrimonio")
    almoxarifado_enabled = module_enabled_for_user(u, "almoxarifado")
    frota_enabled = module_enabled_for_user(u, "frota")
    ouvidoria_enabled = module_enabled_for_user(u, "ouvidoria")
    tributos_enabled = module_enabled_for_user(u, "tributos")

    return {
        "can_org": can(u, "org.view"),
        "can_org_manage_secretaria": can(u, "org.manage_secretaria"),
        "can_edu": can(u, "educacao.view") and edu_enabled,
        "can_avaliacoes": can(u, "avaliacoes.view") and avaliacoes_enabled,
        "can_nee": can(u, "nee.view") and nee_enabled,
        "can_saude": can(u, "saude.view") and saude_enabled,
        "can_users": can(u, "accounts.manage_users"),
        "can_billing": can(u, "billing.view"),
        "can_billing_admin": can(u, "billing.admin"),
        "can_financeiro": can(u, "financeiro.view") and financeiro_enabled,
        "can_processos": can(u, "processos.view") and processos_enabled,
        "can_compras": can(u, "compras.view") and compras_enabled,
        "can_contratos": can(u, "contratos.view") and contratos_enabled,
        "can_integracoes": can(u, "integracoes.view") and integracoes_enabled,
        "can_paineis": can(u, "paineis.view") and paineis_enabled,
        "can_conversor": can(u, "conversor.view") and conversor_enabled,
        "can_rh": can(u, "rh.view") and rh_enabled,
        "can_ponto": can(u, "ponto.view") and ponto_enabled,
        "can_folha": can(u, "folha.view") and folha_enabled,
        "can_patrimonio": can(u, "patrimonio.view") and patrimonio_enabled,
        "can_almoxarifado": can(u, "almoxarifado.view") and almoxarifado_enabled,
        "can_frota": can(u, "frota.view") and frota_enabled,
        "can_ouvidoria": can(u, "ouvidoria.view") and ouvidoria_enabled,
        "can_tributos": can(u, "tributos.view") and tributos_enabled,
        "can_system_admin": can(u, "system.admin_django"),
        "can_edu_manage": can(u, "educacao.manage") and edu_enabled,
        "can_org_municipios": can(u, "org.municipios.view") or can(u, "org.manage") or (getattr(u, "is_superuser", False)),
        "can_publicacoes_admin": can_publicacoes_admin,
        "is_professor_role": is_professor_role,
        "current_municipio_public": getattr(request, "current_municipio", None),
        "is_public_tenant": bool(getattr(request, "is_public_tenant", False)),
        "public_login_url": getattr(request, "public_login_url", "/accounts/login/"),
    }
