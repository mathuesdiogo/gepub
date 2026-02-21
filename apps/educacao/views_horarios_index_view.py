from __future__ import annotations

from django.urls import reverse

from apps.core.rbac import scope_filter_turmas
from apps.core.views_gepub import BaseListViewGepub

from .models import Turma


class HorariosIndexView(BaseListViewGepub):
    template_name = "educacao/horarios_index.html"
    url_name = "educacao:horarios_index"
    perm_required = "educacao.view"

    page_title = "Horários"
    page_subtitle = "Selecione uma turma para visualizar/editar o horário"

    paginate_by = 12
    ordering = "-ano_letivo"

    autocomplete_url_name = "educacao:api_turmas_suggest"

    search_fields = ["nome", "unidade__nome", "unidade__secretaria__nome"]

    def get_base_queryset(self):
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
        )
        qs = scope_filter_turmas(self.request.user, qs)
        return qs

    def apply_ano(self, qs, ano):
        if ano:
            return qs.filter(ano_letivo=ano)
        return qs

    def get_actions(self, *, q: str, ano: int | None, **kwargs):
        return [{
            "label": "Voltar",
            "url": reverse("educacao:index"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }]

    def get_headers(self, **kwargs):
        return [
            {"label": "Turma"},
            {"label": "Ano", "width": "110px"},
            {"label": "Turno", "width": "140px"},
            {"label": "Unidade"},
            {"label": "Secretaria"},
            {"label": "Ação", "width": "180px"},
        ]

    def get_rows(self, objs, **kwargs):
        rows=[]
        for t in objs:
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
        return rows

    def get_extra_filters_html(self, *, q: str, ano: int | None, **kwargs) -> str:
        val = ano or ""
        return f"""
<div class="filter-bar__field">
  <label class="small">Ano letivo</label>
  <input name="ano" value="{val}" placeholder="Ex.: 2026" />
</div>
"""

    def get_input_attrs(self, **kwargs) -> str:
        return (
            'data-autocomplete-url="' + reverse("educacao:api_turmas_suggest") + '" '
            'data-autocomplete-href="' + (reverse("educacao:horarios_index") + '?q={q}') + '"'
        )
