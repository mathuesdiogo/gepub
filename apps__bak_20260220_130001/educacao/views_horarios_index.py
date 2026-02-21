from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import can, scope_filter_turmas

from .models import Turma


@login_required
@require_perm("educacao.view")
def horarios_index(request):
    q = (request.GET.get("q") or "").strip()
    ano = (request.GET.get("ano") or "").strip()

    qs = (
    Turma.objects.select_related("unidade", "unidade__secretaria")
    .only(
        "id",
        "nome",
        "ano_letivo",
        "turno",
        "unidade__nome",
        "unidade__secretaria__nome",
    )
    .order_by("-ano_letivo", "nome")

    )

    if ano.isdigit():
        qs = qs.filter(ano_letivo=int(ano))

    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(unidade__nome__icontains=q)
            | Q(unidade__secretaria__nome__icontains=q)
        )

    qs = scope_filter_turmas(request.user, qs)

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    actions = [
        {
            "label": "Voltar",
            "url": reverse("educacao:index"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }
    ]

    headers = [
        {"label": "Turma"},
        {"label": "Ano", "width": "110px"},
        {"label": "Turno", "width": "140px"},
        {"label": "Unidade"},
        {"label": "Secretaria"},
        {"label": "Ação", "width": "180px"},
    ]

    rows = []
    for t in page_obj:
        rows.append({
            "cells": [
                {"text": t.nome, "url": reverse("educacao:turma_detail", args=[t.pk])},
                {"text": str(t.ano_letivo or "—")},
                {"text": t.get_turno_display() if hasattr(t, "get_turno_display") else (getattr(t, "turno", "") or "—")},
                {"text": getattr(getattr(t, "unidade", None), "nome", "—")},
                {"text": getattr(getattr(getattr(t, "unidade", None), "secretaria", None), "nome", "—")},
                {"text": "Abrir horário", "url": reverse("educacao:horario_turma", args=[t.pk])},
            ],
            "can_edit": False,
            "edit_url": "",
        })

    extra_filters = f"""
      <div class="filter-bar__field">
        <label class="small">Ano letivo</label>
        <input name="ano" value="{ano}" placeholder="Ex.: 2026" />
      </div>
    """

    return render(request, "educacao/horarios_index.html", {
        "q": q,
        "ano": ano,
        "page_obj": page_obj,
        "actions": actions,
        "headers": headers,
        "rows": rows,
        "action_url": reverse("educacao:horarios_index"),
        "clear_url": reverse("educacao:horarios_index"),
        "has_filters": bool(ano),
        "extra_filters": extra_filters,
        # autocomplete opcional (você já tem api_turmas_suggest)
        "autocomplete_url": reverse("educacao:api_turmas_suggest"),
        "autocomplete_href": reverse("educacao:horarios_index") + "?q={q}",
    })
