# apps/core/decorators.py
from __future__ import annotations

from functools import wraps

from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from apps.core.rbac import can, is_admin, is_professor_profile_role, role_scope_base


_PROFESSOR_EDUCACAO_ALLOWED_ROUTES = {
    "educacao:index",
    "educacao:portal_professor",
    "educacao:aluno_list",
    "educacao:aluno_detail",
    "educacao:portal_aluno",
    "educacao:aluno_meus_dados",
    "educacao:historico_aluno",
    "educacao:declaracao_vinculo_pdf",
    "educacao:turma_list",
    "educacao:turma_detail",
    "educacao:boletim_turma",
    "educacao:boletim_aluno",
    "educacao:boletim_turma_periodo",
    "educacao:meus_diarios",
    "educacao:diario_detail",
    "educacao:aula_create",
    "educacao:aula_update",
    "educacao:aula_frequencia",
    "educacao:api_alunos_turma_suggest",
    "educacao:avaliacao_list",
    "educacao:avaliacao_create",
    "educacao:notas_lancar",
    "educacao:justificativa_falta_list",
    "educacao:justificativa_falta_detail",
    "educacao:fechamento_turma_periodo",
    "educacao:professor_inicio",
    "educacao:professor_diarios",
    "educacao:professor_aulas",
    "educacao:professor_frequencias",
    "educacao:professor_notas",
    "educacao:professor_agenda_avaliacoes",
    "educacao:professor_horarios",
    "educacao:professor_planos_ensino",
    "educacao:professor_plano_ensino_editar",
    "educacao:professor_plano_ensino_informatica_editar",
    "educacao:professor_informatica_avaliacoes",
    "educacao:professor_informatica_avaliacao_create",
    "educacao:professor_informatica_notas_lancar",
    "educacao:professor_materiais",
    "educacao:professor_material_novo",
    "educacao:professor_material_editar",
    "educacao:professor_justificativas",
    "educacao:professor_fechamento",
    "educacao:api_turmas_suggest",
    "educacao:api_alunos_suggest",
}

_ALUNO_EDUCACAO_ALLOWED_ROUTES = {
    "educacao:portal_aluno",  # rota legada -> redireciona para a rota oficial
    "educacao:aluno_meus_dados",
    "educacao:aluno_documentos_processos",
    "educacao:aluno_ensino",
    "educacao:aluno_ensino_dados",
    "educacao:aluno_ensino_justificativa",
    "educacao:aluno_ensino_boletins",
    "educacao:aluno_ensino_avaliacoes",
    "educacao:aluno_ensino_disciplinas",
    "educacao:aluno_ensino_horarios",
    "educacao:aluno_ensino_mensagens",
    "educacao:aluno_ensino_biblioteca",
    "educacao:aluno_ensino_apoio",
    "educacao:aluno_ensino_seletivos",
    "educacao:aluno_ensino_renovacao",
    "educacao:aluno_pesquisa",
    "educacao:aluno_central_servicos",
    "educacao:aluno_atividades",
    "educacao:aluno_saude",
    "educacao:aluno_comunicacao",
    "educacao:historico_aluno",
    "educacao:portal_aluno_edital_detail",
    "educacao:declaracao_vinculo_pdf",
    "educacao:carteira_emitir_pdf",
}
_ALUNO_EDUCACAO_ALLOWED_ROUTES_LEAF = {name.split(":", 1)[-1] for name in _ALUNO_EDUCACAO_ALLOWED_ROUTES}


def _is_professor(user) -> bool:
    role = getattr(getattr(user, "profile", None), "role", "")
    return is_professor_profile_role(role)


def _is_aluno(user) -> bool:
    role = getattr(getattr(user, "profile", None), "role", "")
    return role_scope_base(role) == "ALUNO"


def _route_name(request) -> str:
    match = getattr(request, "resolver_match", None)
    if not match:
        return ""
    namespace = (getattr(match, "namespace", "") or "").strip()
    url_name = (getattr(match, "url_name", "") or "").strip()
    if not url_name:
        return ""
    if namespace:
        return f"{namespace}:{url_name}"
    return url_name


def require_perm(perm: str):
    """
    Decorator RBAC:
    - se não logado: redirect para login
    - se logado e sem perm: 403
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = getattr(request, "user", None)

            if not user or not user.is_authenticated:
                # usa o LOGIN_URL do Django, com fallback
                login_url = getattr(settings, "LOGIN_URL", "/accounts/login/")
                return redirect(f"{login_url}?next={request.get_full_path()}")

            if perm == "educacao.view" and _is_aluno(user):
                route_name = _route_name(request)
                route_leaf = route_name.split(":", 1)[-1] if route_name else ""
                if (
                    (route_name and route_name in _ALUNO_EDUCACAO_ALLOWED_ROUTES)
                    or (route_leaf and route_leaf in _ALUNO_EDUCACAO_ALLOWED_ROUTES_LEAF)
                ):
                    return view_func(request, *args, **kwargs)
                return HttpResponseForbidden(
                    "403 — Perfil Aluno possui acesso apenas aos seus dados acadêmicos."
                )

            if not can(user, perm):
                return HttpResponseForbidden("403 — Você não tem permissão para acessar esta página.")

            if perm == "educacao.view" and _is_professor(user):
                route_name = _route_name(request)
                if route_name and route_name not in _PROFESSOR_EDUCACAO_ALLOWED_ROUTES:
                    return HttpResponseForbidden(
                        "403 — Perfil Professor possui acesso apenas a Alunos, Turmas, Diário, Aulas e Notas."
                    )

            return view_func(request, *args, **kwargs)

        return _wrapped
    return decorator


def require_plan_feature(*features: str, any_of: bool = True, allow_without_plan: bool = True, message: str | None = None):
    """
    Exige feature(s) do plano ativo para acessar uma view.
    """
    normalized = {str(f or "").strip() for f in features if str(f or "").strip()}

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = getattr(request, "user", None)

            if not user or not user.is_authenticated:
                login_url = getattr(settings, "LOGIN_URL", "/accounts/login/")
                return redirect(f"{login_url}?next={request.get_full_path()}")

            if not normalized or is_admin(user):
                return view_func(request, *args, **kwargs)

            profile = getattr(user, "profile", None)
            municipio = getattr(profile, "municipio", None) if profile else None

            try:
                from apps.billing.services import municipio_plan_features
            except Exception:
                if allow_without_plan:
                    return view_func(request, *args, **kwargs)
                return HttpResponseForbidden(message or "403 — Recurso indisponível no plano atual.")

            features_ativas = municipio_plan_features(municipio)
            if not features_ativas and allow_without_plan:
                return view_func(request, *args, **kwargs)

            ok = bool(normalized.intersection(features_ativas)) if any_of else normalized.issubset(features_ativas)
            if not ok:
                return HttpResponseForbidden(message or "403 — Recurso indisponível no plano atual.")

            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
