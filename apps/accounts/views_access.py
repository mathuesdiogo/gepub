from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from apps.core.decorators import require_perm
from apps.core.exports import export_csv
from apps.core.rbac import role_scope_base

from .forms_access import AccessPreviewForm
from .models import AccessPreviewLog
from .services_access_matrix import (
    available_app_options,
    available_category_options,
    build_app_overview,
    build_role_access_matrix,
    filter_role_access_matrix,
)

ACCESS_PREVIEW_SESSION_KEY = "gepub_access_preview"


def _is_platform_admin(user) -> bool:
    profile = getattr(user, "profile", None)
    return bool(getattr(user, "is_superuser", False) or role_scope_base(getattr(profile, "role", None)) == "ADMIN")


def _safe_next(request, fallback: str) -> str:
    next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}):
        return next_url
    return fallback


def _render_apps_html(apps: list[dict]) -> str:
    if not apps:
        return '<span class="status default">Sem apps</span>'
    return " ".join(
        f'<span class="status info">{app["app_label"]} ({app["action_summary"]})</span>'
        for app in apps
    )


def _render_manager_roles_html(labels: list[str]) -> str:
    if not labels:
        return '<span class="status default">Não atribuível</span>'
    return " ".join(f'<span class="status success">{label}</span>' for label in labels)


def _row_for_table(row: dict) -> dict:
    profile_badges = [f'<span class="status info">{row["role_code"]}</span>']
    if row.get("is_profile_choice"):
        profile_badges.append('<span class="status success">Disponível no cadastro</span>')
    else:
        profile_badges.append('<span class="status warning">Apenas motor RBAC</span>')

    profile_cell = "<div><strong>{}</strong><div class=\"small\">{}</div><div>{}</div></div>".format(
        row["role_label"],
        row["role_code"],
        " ".join(profile_badges),
    )

    permission_samples = row["permissions"][:5]
    perms_html = "<div><strong>{}</strong><div class=\"small\">{}</div></div>".format(
        row["permissions_count"],
        "<br>".join(permission_samples) if permission_samples else "Sem permissões explícitas",
    )

    return {
        "cells": [
            {"html": profile_cell},
            {"text": row["category_label"]},
            {"text": row["scope_base"]},
            {"html": _render_apps_html(row["apps"])},
            {"html": perms_html},
            {"html": _render_manager_roles_html(row["managed_by_labels"])},
        ]
    }


@login_required
@require_perm("accounts.manage_users")
def acessos_matriz(request):
    if not _is_platform_admin(request.user):
        return HttpResponseForbidden("Você não tem permissão para acessar o mapa institucional de acessos.")

    q = (request.GET.get("q") or "").strip()
    category = (request.GET.get("category") or "").strip().lower()
    app_key = (request.GET.get("app") or "").strip().lower()
    export = (request.GET.get("export") or "").strip().lower()

    matrix_all = build_role_access_matrix(include_engine_roles=True)
    rows = filter_role_access_matrix(matrix_all, q=q, category=category, app_key=app_key)

    if export == "csv":
        export_rows = []
        for row in rows:
            export_rows.append(
                [
                    row["role_label"],
                    row["role_code"],
                    row["category_label"],
                    row["scope_base"],
                    ", ".join(app["app_label"] for app in row["apps"]),
                    ", ".join(row["permissions"]),
                    ", ".join(row["managed_by_labels"]),
                    "SIM" if row.get("is_profile_choice") else "NAO",
                ]
            )
        return export_csv(
            "gepub_mapa_acessos.csv",
            headers=[
                "Perfil",
                "Código",
                "Categoria",
                "Escopo base",
                "Apps",
                "Permissões",
                "Perfis que podem atribuir",
                "Disponível no cadastro",
            ],
            rows=export_rows,
        )

    app_cards = build_app_overview(rows)

    paginator = Paginator(rows, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    table_rows = [_row_for_table(item) for item in page_obj.object_list]

    actions = [
        {
            "label": "Simular perfil",
            "url": reverse("accounts:acessos_simular"),
            "icon": "fa-solid fa-eye",
            "variant": "gp-button--primary",
        },
        {
            "label": "Exportar CSV",
            "url": f"{request.path}?q={q}&category={category}&app={app_key}&export=csv",
            "icon": "fa-solid fa-file-export",
            "variant": "gp-button--outline",
        },
    ]

    headers = [
        {"label": "Perfil / função"},
        {"label": "Categoria"},
        {"label": "Escopo base"},
        {"label": "Apps e capacidades"},
        {"label": "Permissões"},
        {"label": "Atribuído por"},
    ]

    return render(
        request,
        "accounts/access_matrix.html",
        {
            "title": "Mapa institucional de acessos",
            "subtitle": "Papéis, capacidades por app, escopos e cadeia de atribuição",
            "actions": actions,
            "q": q,
            "category": category,
            "app": app_key,
            "category_options": available_category_options(matrix_all),
            "app_options": available_app_options(matrix_all),
            "app_cards": app_cards,
            "headers": headers,
            "rows": table_rows,
            "page_obj": page_obj,
        },
    )


@login_required
@require_perm("accounts.manage_users")
def acessos_simular(request):
    if not _is_platform_admin(request.user):
        return HttpResponseForbidden("Somente administrador da plataforma pode iniciar visualização administrativa.")

    current_payload = request.session.get(ACCESS_PREVIEW_SESSION_KEY) or {}

    initial = {
        "mode": current_payload.get("mode", "profile"),
        "role": current_payload.get("role", ""),
        "target_user": current_payload.get("target_user_id") or None,
        "municipio": (current_payload.get("scope") or {}).get("municipio_id"),
        "secretaria": (current_payload.get("scope") or {}).get("secretaria_id"),
        "unidade": (current_payload.get("scope") or {}).get("unidade_id"),
        "setor": (current_payload.get("scope") or {}).get("setor_id"),
        "local_estrutural": (current_payload.get("scope") or {}).get("local_estrutural_id"),
        "next": request.GET.get("next", ""),
    }

    form = AccessPreviewForm(request.POST or None, actor_user=request.user, initial=initial)

    if request.method == "POST" and form.is_valid():
        payload = form.build_payload()
        request.session[ACCESS_PREVIEW_SESSION_KEY] = payload
        request.session.modified = True

        AccessPreviewLog.objects.create(
            actor=request.user,
            action=AccessPreviewLog.Action.START,
            preview_type=payload.get("preview_type", AccessPreviewLog.PreviewType.PROFILE),
            target_role=payload.get("role", ""),
            target_user_id=payload.get("target_user_id") or None,
            scope_type=payload.get("scope_type", "global"),
            scope_payload=payload.get("scope") or {},
            read_only=bool(payload.get("read_only", True)),
            notes=f"Modo={payload.get('mode', '')}",
        )

        messages.success(
            request,
            "Visualização administrativa ativada em modo leitura. Use o banner superior para encerrar quando finalizar.",
        )
        return redirect(_safe_next(request, reverse("core:dashboard")))

    actions = [
        {
            "label": "Ver mapa de acessos",
            "url": reverse("accounts:acessos_matriz"),
            "icon": "fa-solid fa-network-wired",
            "variant": "gp-button--outline",
        },
        {
            "label": "Encerrar visualização",
            "url": reverse("accounts:acessos_simular_encerrar"),
            "icon": "fa-solid fa-power-off",
            "variant": "gp-button--danger",
        },
    ]

    recent_logs = list(
        AccessPreviewLog.objects.select_related("actor", "target_user")
        .order_by("-created_at")[:15]
    )

    return render(
        request,
        "accounts/access_preview.html",
        {
            "title": "Visualização administrativa",
            "subtitle": "Simule perfis, funções e contextos sem acessar conta real do usuário",
            "actions": actions,
            "form": form,
            "current_payload": current_payload,
            "recent_logs": recent_logs,
        },
    )


@login_required
@require_perm("accounts.manage_users")
def acessos_simular_encerrar(request):
    if not _is_platform_admin(request.user):
        return HttpResponseForbidden("Somente administrador da plataforma pode encerrar visualização administrativa.")

    payload = request.session.pop(ACCESS_PREVIEW_SESSION_KEY, None)
    request.session.modified = True

    if payload:
        AccessPreviewLog.objects.create(
            actor=request.user,
            action=AccessPreviewLog.Action.STOP,
            preview_type=payload.get("preview_type", AccessPreviewLog.PreviewType.PROFILE),
            target_role=payload.get("role", ""),
            target_user_id=payload.get("target_user_id") or None,
            scope_type=payload.get("scope_type", "global"),
            scope_payload=payload.get("scope") or {},
            read_only=bool(payload.get("read_only", True)),
            notes="Encerramento manual da visualização",
        )
        messages.info(request, "Visualização administrativa encerrada.")
    else:
        messages.info(request, "Não havia visualização ativa.")

    return redirect(_safe_next(request, reverse("accounts:acessos_simular")))
