from __future__ import annotations

from collections import defaultdict
from datetime import date
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.exports import export_csv
from apps.core.rbac import can

from .views_users_common import (
    User,
    build_filter_scopes,
    build_querystring,
    scope_users_queryset,
)

ROLE_LABELS = {
    "ADMIN": "Admin",
    "MUNICIPAL": "Gestor Municipal",
    "SECRETARIA": "Gestor de Secretaria",
    "UNIDADE": "Gestor de Unidade",
    "PROFESSOR": "Professor",
    "ALUNO": "Aluno",
    "NEE": "Técnico NEE",
    "LEITURA": "Leitura",
}

GROUP_MODE_OPTIONS = [
    ("lista", "Lista"),
    ("role", "Agrupar por função"),
    ("municipio", "Agrupar por município"),
    ("unidade", "Agrupar por unidade"),
]


def _status_slug(profile, user) -> str:
    if profile and getattr(profile, "bloqueado", False):
        return "BLOQUEADO"
    if profile and getattr(profile, "ativo", False) and getattr(user, "is_active", False):
        return "ATIVO"
    return "INATIVO"


def _status_badge_html(profile, user) -> str:
    slug = _status_slug(profile, user)
    if slug == "BLOQUEADO":
        return '<span class="status danger">Bloqueado</span>'
    if slug == "ATIVO":
        return '<span class="status success">Ativo</span>'
    return '<span class="status default">Inativo</span>'


def _date_or_none(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _build_select_html(*, name: str, label: str, options: list[tuple], selected: str, all_label: str) -> str:
    opts = [f'<option value="">{all_label}</option>']
    for value, text in options:
        value_str = str(value)
        sel = " selected" if selected and selected == value_str else ""
        opts.append(f'<option value="{value_str}"{sel}>{text}</option>')
    return (
        '<div class="filter-bar__field">'
        f'<label class="small">{label}</label>'
        f'<select name="{name}">{"".join(opts)}</select>'
        "</div>"
    )


def _build_date_html(*, name: str, label: str, selected: str) -> str:
    val = selected or ""
    return (
        '<div class="filter-bar__field">'
        f'<label class="small">{label}</label>'
        f'<input type="date" name="{name}" value="{val}">'
        "</div>"
    )


def _build_group_cards(qs, modo: str):
    grouped = defaultdict(list)
    for user in qs:
        p = getattr(user, "profile", None)
        if modo == "role":
            key = ROLE_LABELS.get((getattr(p, "role", "") or "").upper(), "Sem função")
        elif modo == "municipio":
            key = str(getattr(p, "municipio", None) or "Sem município")
        elif modo == "unidade":
            key = str(getattr(p, "unidade", None) or "Sem unidade")
        else:
            key = "Todos"
        grouped[key].append(user)

    cards = []
    for key, users in grouped.items():
        ativos = 0
        inativos = 0
        bloqueados = 0
        for user in users:
            status = _status_slug(getattr(user, "profile", None), user)
            if status == "ATIVO":
                ativos += 1
            elif status == "BLOQUEADO":
                bloqueados += 1
            else:
                inativos += 1
        cards.append(
            {
                "title": key,
                "total": len(users),
                "ativos": ativos,
                "inativos": inativos,
                "bloqueados": bloqueados,
                "users": [
                    {
                        "name": (u.get_full_name() or u.username).strip(),
                        "code": (getattr(getattr(u, "profile", None), "codigo_acesso", "") or "sem código"),
                    }
                    for u in users[:6]
                ],
            }
        )
    cards.sort(key=lambda c: (c["title"] or "").lower())
    return cards


def _export_users_xlsx(*, rows: list[list[str]]) -> HttpResponse:
    try:
        from openpyxl import Workbook
    except Exception:
        headers = ["Nome", "Username", "E-mail", "Código", "Função", "Município", "Secretaria", "Unidade", "Setor", "Status"]
        return export_csv("usuarios.xlsx.csv", headers=headers, rows=rows)

    wb = Workbook()
    ws = wb.active
    ws.title = "Usuarios"
    ws.append(["Nome", "Username", "E-mail", "Código", "Função", "Município", "Secretaria", "Unidade", "Setor", "Status"])
    for r in rows:
        ws.append(r)
    buf = BytesIO()
    wb.save(buf)
    response = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="usuarios.xlsx"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@require_perm("accounts.manage_users")
def usuarios_list(request):
    q = (request.GET.get("q") or "").strip()
    role = (request.GET.get("role") or "").strip().upper()
    municipio = (request.GET.get("municipio") or "").strip()
    secretaria = (request.GET.get("secretaria") or "").strip()
    unidade = (request.GET.get("unidade") or "").strip()
    setor = (request.GET.get("setor") or "").strip()
    status = (request.GET.get("status") or "").strip().upper()
    modo = (request.GET.get("modo") or "lista").strip().lower()
    created_from = (request.GET.get("created_from") or "").strip()
    created_to = (request.GET.get("created_to") or "").strip()
    last_login_from = (request.GET.get("last_login_from") or "").strip()
    last_login_to = (request.GET.get("last_login_to") or "").strip()
    export = (request.GET.get("export") or "").strip().lower()

    filter_params = {
        "q": q,
        "role": role,
        "municipio": municipio,
        "secretaria": secretaria,
        "unidade": unidade,
        "setor": setor,
        "status": status,
        "modo": modo,
        "created_from": created_from,
        "created_to": created_to,
        "last_login_from": last_login_from,
        "last_login_to": last_login_to,
    }

    qs = scope_users_queryset(request)
    if q:
        qs = qs.filter(
            Q(username__icontains=q)
            | Q(email__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(profile__codigo_acesso__icontains=q)
        )
    if role:
        qs = qs.filter(profile__role=role)
    if municipio.isdigit():
        qs = qs.filter(profile__municipio_id=int(municipio))
    if secretaria.isdigit():
        qs = qs.filter(profile__secretaria_id=int(secretaria))
    if unidade.isdigit():
        qs = qs.filter(profile__unidade_id=int(unidade))
    if setor.isdigit():
        qs = qs.filter(profile__setor_id=int(setor))

    created_from_date = _date_or_none(created_from)
    created_to_date = _date_or_none(created_to)
    last_login_from_date = _date_or_none(last_login_from)
    last_login_to_date = _date_or_none(last_login_to)

    if created_from_date:
        qs = qs.filter(date_joined__date__gte=created_from_date)
    if created_to_date:
        qs = qs.filter(date_joined__date__lte=created_to_date)
    if last_login_from_date:
        qs = qs.filter(last_login__date__gte=last_login_from_date)
    if last_login_to_date:
        qs = qs.filter(last_login__date__lte=last_login_to_date)

    if status == "ATIVO":
        qs = qs.filter(profile__ativo=True, profile__bloqueado=False, is_active=True)
    elif status == "INATIVO":
        qs = qs.filter(Q(profile__ativo=False) | Q(is_active=False), profile__bloqueado=False)
    elif status == "BLOQUEADO":
        qs = qs.filter(profile__bloqueado=True)

    qs = qs.order_by("first_name", "last_name", "username")

    if export in {"csv", "xlsx"}:
        rows_export = []
        for u in qs:
            p = getattr(u, "profile", None)
            rows_export.append(
                [
                    (u.get_full_name() or u.username).strip(),
                    u.username or "",
                    u.email or "",
                    getattr(p, "codigo_acesso", "") or "",
                    p.get_role_display() if p and getattr(p, "role", "") else "",
                    str(getattr(p, "municipio", "") or ""),
                    str(getattr(p, "secretaria", "") or ""),
                    str(getattr(p, "unidade", "") or ""),
                    str(getattr(p, "setor", "") or ""),
                    _status_slug(p, u),
                ]
            )
        if export == "csv":
            headers = ["Nome", "Username", "E-mail", "Código", "Função", "Município", "Secretaria", "Unidade", "Setor", "Status"]
            return export_csv("usuarios.csv", headers=headers, rows=rows_export)
        return _export_users_xlsx(rows=rows_export)

    can_manage = can(request.user, "accounts.manage_users") or request.user.is_staff or request.user.is_superuser
    base_qs = build_querystring(filter_params)
    qs_prefix = f"?{base_qs}" if base_qs else ""

    actions = []
    if can_manage:
        actions.append(
            {
                "label": "Novo usuário",
                "url": reverse("accounts:usuario_create"),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            }
        )
    actions.extend(
        [
            {
                "label": "CSV",
                "url": reverse("accounts:usuarios_list") + "?" + build_querystring(filter_params, export="csv"),
                "icon": "fa-solid fa-file-csv",
                "variant": "btn--ghost",
            },
            {
                "label": "XLSX",
                "url": reverse("accounts:usuarios_list") + "?" + build_querystring(filter_params, export="xlsx"),
                "icon": "fa-solid fa-file-excel",
                "variant": "btn--ghost",
            },
        ]
    )

    headers = [
        {"label": "Nome"},
        {"label": "Código", "width": "140px"},
        {"label": "Função", "width": "180px"},
        {"label": "Município"},
        {"label": "Secretaria"},
        {"label": "Unidade"},
        {"label": "Setor"},
        {"label": "Status", "width": "120px"},
    ]

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    rows = []
    for u in page_obj:
        p = getattr(u, "profile", None)
        is_ativo = bool(getattr(p, "ativo", False))
        is_bloqueado = bool(getattr(p, "bloqueado", False))
        rows.append(
            {
                "obj": u,
                "is_ativo": is_ativo,
                "is_bloqueado": is_bloqueado,
                "cells": [
                    {"text": (u.get_full_name() or u.username).strip(), "url": reverse("accounts:usuario_detail", args=[u.id])},
                    {"text": getattr(p, "codigo_acesso", "") or "—"},
                    {"text": p.get_role_display() if p and getattr(p, "role", "") else "—"},
                    {"text": str(getattr(p, "municipio", "") or "—")},
                    {"text": str(getattr(p, "secretaria", "") or "—")},
                    {"text": str(getattr(p, "unidade", "") or "—")},
                    {"text": str(getattr(p, "setor", "") or "—")},
                    {"html": _status_badge_html(p, u), "safe": True},
                ],
            }
        )

    grouped_cards = _build_group_cards(qs, modo) if modo in {"role", "municipio", "unidade"} else []

    scopes = build_filter_scopes(
        request,
        municipio_id=municipio,
        secretaria_id=secretaria,
        unidade_id=unidade,
    )
    extra_filters = "".join(
        [
            _build_select_html(
                name="modo",
                label="Visualização",
                options=[(k, v) for k, v in GROUP_MODE_OPTIONS if k != "lista"],
                selected=modo,
                all_label="Lista",
            ),
            _build_select_html(
                name="role",
                label="Função",
                options=[(k, v) for k, v in ROLE_LABELS.items()],
                selected=role,
                all_label="Todas as funções",
            ),
            _build_select_html(
                name="status",
                label="Status",
                options=[("ATIVO", "Ativo"), ("INATIVO", "Inativo"), ("BLOQUEADO", "Bloqueado")],
                selected=status,
                all_label="Todos os status",
            ),
            _build_select_html(
                name="municipio",
                label="Município",
                options=scopes["municipios"],
                selected=municipio,
                all_label="Todos os municípios",
            ),
            _build_select_html(
                name="secretaria",
                label="Secretaria",
                options=scopes["secretarias"],
                selected=secretaria,
                all_label="Todas as secretarias",
            ),
            _build_select_html(
                name="unidade",
                label="Unidade",
                options=scopes["unidades"],
                selected=unidade,
                all_label="Todas as unidades",
            ),
            _build_select_html(
                name="setor",
                label="Setor",
                options=scopes["setores"],
                selected=setor,
                all_label="Todos os setores",
            ),
            _build_date_html(name="created_from", label="Criado de", selected=created_from),
            _build_date_html(name="created_to", label="Criado até", selected=created_to),
            _build_date_html(name="last_login_from", label="Login de", selected=last_login_from),
            _build_date_html(name="last_login_to", label="Login até", selected=last_login_to),
        ]
    )

    autocomplete_url = reverse("accounts:users_autocomplete")
    autocomplete_href = reverse("accounts:usuarios_list") + "?q={q}"
    input_attrs = f'data-autocomplete-url="{autocomplete_url}" data-autocomplete-href="{autocomplete_href}"'

    has_filters = any(
        [
            q,
            role,
            municipio,
            secretaria,
            unidade,
            setor,
            status,
            created_from,
            created_to,
            last_login_from,
            last_login_to,
            modo not in {"", "lista"},
        ]
    )

    return render(
        request,
        "accounts/users_list.html",
        {
            "q": q,
            "modo": modo,
            "page_obj": page_obj,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "grouped_cards": grouped_cards,
            "actions_partial": "accounts/partials/user_row_actions.html",
            "action_url": reverse("accounts:usuarios_list"),
            "clear_url": reverse("accounts:usuarios_list"),
            "has_filters": has_filters,
            "extra_filters": extra_filters,
            "autocomplete_url": autocomplete_url,
            "autocomplete_href": autocomplete_href,
            "input_attrs": input_attrs,
            "next_url": reverse("accounts:usuarios_list") + qs_prefix,
        },
    )


@login_required
@require_perm("accounts.manage_users")
def users_autocomplete(request):
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    qs = scope_users_queryset(request)
    qs = qs.filter(
        Q(username__icontains=q)
        | Q(email__icontains=q)
        | Q(first_name__icontains=q)
        | Q(last_name__icontains=q)
        | Q(profile__codigo_acesso__icontains=q)
    ).order_by("first_name", "last_name", "username")[:10]

    results = []
    for u in qs:
        p = getattr(u, "profile", None)
        nome = (u.get_full_name() or u.username).strip()
        meta = f'{u.email or "sem e-mail"} • {getattr(p, "codigo_acesso", "") or "sem código"}'
        results.append({"id": u.id, "text": nome, "meta": meta})

    return JsonResponse({"results": results})
