# apps/core/decorators.py
from __future__ import annotations

from functools import wraps

from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from apps.core.rbac import can


_PROFESSOR_EDUCACAO_ALLOWED_ROUTES = {
    "educacao:index",
    "educacao:portal_professor",
    "educacao:aluno_list",
    "educacao:aluno_detail",
    "educacao:portal_aluno",
    "educacao:historico_aluno",
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
    "educacao:api_turmas_suggest",
    "educacao:api_alunos_suggest",
}


def _is_professor(user) -> bool:
    role = (getattr(getattr(user, "profile", None), "role", "") or "").upper()
    return role == "PROFESSOR"


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
