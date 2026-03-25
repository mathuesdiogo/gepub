# apps/core/context_processors.py
from __future__ import annotations

from django.urls import reverse

from apps.billing.services import PlanoApp, municipio_has_plan_app
from apps.core.design_system import THEME_OPTIONS, resolve_admin_theme_context, token_overrides_to_style
from apps.core.module_access import module_enabled_for_user
from apps.core.rbac import can, get_profile, role_scope_base


def permissions(request):
    """Permissões usadas nos templates (menu/sidebar).

    Mantém as chaves esperadas pelo seu base.html e telas de Educação.
    """
    u = getattr(request, "user", None)
    profile = get_profile(u)
    role = getattr(profile, "role", "")
    role_code = ((role or "") + "").strip().upper()
    municipio = getattr(profile, "municipio", None)
    role_base = role_scope_base(role)
    is_professor_role = role_base == "PROFESSOR"
    plan_portal_enabled = bool(getattr(u, "is_superuser", False)) or municipio_has_plan_app(municipio, PlanoApp.PORTAL)
    plan_transparencia_enabled = bool(getattr(u, "is_superuser", False)) or municipio_has_plan_app(
        municipio,
        PlanoApp.TRANSPARENCIA,
    )
    plan_camara_enabled = bool(getattr(u, "is_superuser", False)) or municipio_has_plan_app(municipio, PlanoApp.CAMARA)
    can_publicacoes_admin = (
        plan_portal_enabled
        and (
            bool(getattr(u, "is_superuser", False))
        or (can(u, "org.view") and role_base in {"ADMIN", "MUNICIPAL", "SECRETARIA"})
        )
    )
    edu_enabled = module_enabled_for_user(u, "educacao")
    avaliacoes_enabled = module_enabled_for_user(u, "avaliacoes")
    nee_enabled = module_enabled_for_user(u, "nee")
    saude_enabled = module_enabled_for_user(u, "saude")
    financeiro_enabled = module_enabled_for_user(u, "financeiro")
    processos_enabled = module_enabled_for_user(u, "processos")
    compras_enabled = module_enabled_for_user(u, "compras")
    contratos_enabled = module_enabled_for_user(u, "contratos")
    integracoes_enabled = module_enabled_for_user(u, "integracoes")
    comunicacao_enabled = module_enabled_for_user(u, "comunicacao")
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
    camara_enabled = module_enabled_for_user(u, "camara")
    ds_theme_ctx = resolve_admin_theme_context(request)
    meus_dados_url = ""
    aluno_historico_url = ""
    aluno_documentos_processos_url = ""
    aluno_ensino_url = ""
    aluno_ensino_dados_url = ""
    aluno_ensino_justificativa_url = ""
    aluno_ensino_boletins_url = ""
    aluno_ensino_avaliacoes_url = ""
    aluno_ensino_disciplinas_url = ""
    aluno_ensino_horarios_url = ""
    aluno_ensino_mensagens_url = ""
    aluno_ensino_biblioteca_url = ""
    aluno_ensino_apoio_url = ""
    aluno_ensino_seletivos_url = ""
    aluno_pesquisa_url = ""
    aluno_central_servicos_url = ""
    aluno_atividades_url = ""
    aluno_saude_url = ""
    aluno_comunicacao_url = ""
    access_preview = getattr(request, "access_preview_context", {}) or {}
    aluno_id = getattr(profile, "aluno_id", None)
    if aluno_id:
        codigo_aluno = (
            (getattr(profile, "codigo_acesso", "") or "").strip()
            or (getattr(u, "username", "") or "").strip()
            or str(aluno_id)
        )
        try:
            meus_dados_url = reverse("educacao:aluno_meus_dados", args=[codigo_aluno])
        except Exception:
            meus_dados_url = ""
        try:
            aluno_historico_url = reverse("educacao:historico_aluno", args=[aluno_id])
        except Exception:
            aluno_historico_url = ""
        try:
            aluno_documentos_processos_url = reverse("educacao:aluno_documentos_processos", args=[codigo_aluno])
        except Exception:
            aluno_documentos_processos_url = ""
        try:
            aluno_ensino_url = reverse("educacao:aluno_ensino", args=[codigo_aluno])
        except Exception:
            aluno_ensino_url = ""
        try:
            aluno_ensino_dados_url = reverse("educacao:aluno_ensino_dados", args=[codigo_aluno])
        except Exception:
            aluno_ensino_dados_url = ""
        try:
            aluno_ensino_justificativa_url = reverse("educacao:aluno_ensino_justificativa", args=[codigo_aluno])
        except Exception:
            aluno_ensino_justificativa_url = ""
        try:
            aluno_ensino_boletins_url = reverse("educacao:aluno_ensino_boletins", args=[codigo_aluno])
        except Exception:
            aluno_ensino_boletins_url = ""
        try:
            aluno_ensino_avaliacoes_url = reverse("educacao:aluno_ensino_avaliacoes", args=[codigo_aluno])
        except Exception:
            aluno_ensino_avaliacoes_url = ""
        try:
            aluno_ensino_disciplinas_url = reverse("educacao:aluno_ensino_disciplinas", args=[codigo_aluno])
        except Exception:
            aluno_ensino_disciplinas_url = ""
        try:
            aluno_ensino_horarios_url = reverse("educacao:aluno_ensino_horarios", args=[codigo_aluno])
        except Exception:
            aluno_ensino_horarios_url = ""
        try:
            aluno_ensino_mensagens_url = reverse("educacao:aluno_ensino_mensagens", args=[codigo_aluno])
        except Exception:
            aluno_ensino_mensagens_url = ""
        try:
            aluno_ensino_biblioteca_url = reverse("educacao:aluno_ensino_biblioteca", args=[codigo_aluno])
        except Exception:
            aluno_ensino_biblioteca_url = ""
        try:
            aluno_ensino_apoio_url = reverse("educacao:aluno_ensino_apoio", args=[codigo_aluno])
        except Exception:
            aluno_ensino_apoio_url = ""
        try:
            aluno_ensino_seletivos_url = reverse("educacao:aluno_ensino_seletivos", args=[codigo_aluno])
        except Exception:
            aluno_ensino_seletivos_url = ""
        try:
            aluno_pesquisa_url = reverse("educacao:aluno_pesquisa", args=[codigo_aluno])
        except Exception:
            aluno_pesquisa_url = ""
        try:
            aluno_central_servicos_url = reverse("educacao:aluno_central_servicos", args=[codigo_aluno])
        except Exception:
            aluno_central_servicos_url = ""
        try:
            aluno_atividades_url = reverse("educacao:aluno_atividades", args=[codigo_aluno])
        except Exception:
            aluno_atividades_url = ""
        try:
            aluno_saude_url = reverse("educacao:aluno_saude", args=[codigo_aluno])
        except Exception:
            aluno_saude_url = ""
        try:
            aluno_comunicacao_url = reverse("educacao:aluno_comunicacao", args=[codigo_aluno])
        except Exception:
            aluno_comunicacao_url = ""

    return {
        "can_org": can(u, "org.view"),
        "can_org_manage_secretaria": can(u, "org.manage_secretaria"),
        "can_edu": can(u, "educacao.view") and edu_enabled,
        "can_avaliacoes": can(u, "avaliacoes.view") and avaliacoes_enabled,
        "can_nee": can(u, "nee.view") and nee_enabled,
        "can_saude": can(u, "saude.view") and saude_enabled,
        "can_users": can(u, "accounts.manage_users"),
        "can_exclusoes": bool(
            getattr(u, "is_superuser", False)
            or can(u, "accounts.manage_users")
            or can(u, "org.manage_secretaria")
            or can(u, "org.manage_unidade")
        ),
        "can_billing": can(u, "billing.view"),
        "can_billing_admin": can(u, "billing.admin"),
        "can_financeiro": can(u, "financeiro.view") and financeiro_enabled,
        "can_processos": can(u, "processos.view") and processos_enabled,
        "can_compras": can(u, "compras.view") and compras_enabled,
        "can_contratos": can(u, "contratos.view") and contratos_enabled,
        "can_integracoes": can(u, "integracoes.view") and integracoes_enabled,
        "can_comunicacao": can(u, "comunicacao.view") and comunicacao_enabled,
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
        "can_camara": can(u, "camara.view") and camara_enabled and plan_camara_enabled,
        "can_system_admin": can(u, "system.admin_django"),
        "can_edu_manage": can(u, "educacao.manage") and edu_enabled,
        "can_org_municipios": can(u, "org.municipios.view") or can(u, "org.manage") or (getattr(u, "is_superuser", False)),
        "can_publicacoes_admin": can_publicacoes_admin,
        "plan_portal_enabled": plan_portal_enabled,
        "plan_transparencia_enabled": plan_transparencia_enabled,
        "plan_camara_enabled": plan_camara_enabled,
        "is_professor_role": is_professor_role,
        "role_scope_base": role_base,
        "role_code": role_code,
        "current_municipio_public": getattr(request, "current_municipio", None),
        "is_public_tenant": bool(getattr(request, "is_public_tenant", False)),
        "public_login_url": getattr(request, "public_login_url", "/accounts/login/"),
        "gepub_active_theme": ds_theme_ctx.theme,
        "gepub_ds_version": ds_theme_ctx.version,
        "gepub_theme_lock": ds_theme_ctx.lock_theme_for_users,
        "gepub_theme_allow_user_override": ds_theme_ctx.allow_user_theme_override,
        "gepub_theme_tokens_override": ds_theme_ctx.token_overrides,
        "gepub_theme_tokens_style": token_overrides_to_style(ds_theme_ctx.token_overrides),
        "gepub_theme_options": THEME_OPTIONS,
        "meus_dados_url": meus_dados_url,
        "aluno_historico_url": aluno_historico_url,
        "aluno_documentos_processos_url": aluno_documentos_processos_url,
        "aluno_ensino_url": aluno_ensino_url,
        "aluno_ensino_dados_url": aluno_ensino_dados_url,
        "aluno_ensino_justificativa_url": aluno_ensino_justificativa_url,
        "aluno_ensino_boletins_url": aluno_ensino_boletins_url,
        "aluno_ensino_avaliacoes_url": aluno_ensino_avaliacoes_url,
        "aluno_ensino_disciplinas_url": aluno_ensino_disciplinas_url,
        "aluno_ensino_horarios_url": aluno_ensino_horarios_url,
        "aluno_ensino_mensagens_url": aluno_ensino_mensagens_url,
        "aluno_ensino_biblioteca_url": aluno_ensino_biblioteca_url,
        "aluno_ensino_apoio_url": aluno_ensino_apoio_url,
        "aluno_ensino_seletivos_url": aluno_ensino_seletivos_url,
        "aluno_pesquisa_url": aluno_pesquisa_url,
        "aluno_central_servicos_url": aluno_central_servicos_url,
        "aluno_atividades_url": aluno_atividades_url,
        "aluno_saude_url": aluno_saude_url,
        "aluno_comunicacao_url": aluno_comunicacao_url,
        "access_preview_active": bool(access_preview.get("active")),
        "access_preview_role": access_preview.get("role_label", ""),
        "access_preview_scope": access_preview.get("scope_label", ""),
        "access_preview_mode": access_preview.get("mode_label", ""),
        "access_preview_target": access_preview.get("target_user_label", ""),
    }
