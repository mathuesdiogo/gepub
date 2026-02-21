from __future__ import annotations

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.core.rbac import can, scope_filter_turmas
from apps.core.views_gepub import BaseListViewGepub

from .models import Turma


class HorariosIndexView(BaseListViewGepub):
    template_name = "educacao/horarios_index.html"
    url_name = "educacao:horarios_index"

    page_title = "Horários"
    page_subtitle = "Selecione uma turma para ver/editar a grade"

    paginate_by = 20
    default_ano = timezone.now().year

    def get_base_queryset(self):
        qs = (
            Turma.objects.select_related("unidade", "unidade__secretaria")
            .only(
                "id", "nome", "ano_letivo", "turno",
                "unidade__nome", "unidade__secretaria__nome",
            )
            .order_by("-ano_letivo", "nome")
        )
        return scope_filter_turmas(self.request.user, qs)

    def apply_ano(self, qs, ano, **kwargs):
        if ano:
            return qs.filter(ano_letivo=int(ano))
        return qs

    def apply_search(self, qs, q: str, **kwargs):
        if not q:
            return qs
        return qs.filter(
            Q(nome__icontains=q)
            | Q(unidade__nome__icontains=q)
            | Q(unidade__secretaria__nome__icontains=q)
        )

    def get_actions(self, **kwargs):
        # pode ter botão global se quiser, mas mantemos vazio
        return []

    def get_headers(self, **kwargs):
        return [
            {"label": "Turma"},
            {"label": "Ano", "width": "110px"},
            {"label": "Turno", "width": "140px"},
            {"label": "Unidade"},
            {"label": "Secretaria"},
        ]

    def get_rows(self, objs, **kwargs):
        rows = []
        for t in objs:
            rows.append({
                "cells": [
                    {"text": t.nome, "url": reverse("educacao:horario_turma", args=[t.pk])},
                    {"text": str(t.ano_letivo)},
                    {"text": t.get_turno_display() if hasattr(t, "get_turno_display") else (getattr(t, "turno", "") or "—")},
                    {"text": getattr(getattr(t, "unidade", None), "nome", "—")},
                    {"text": getattr(getattr(getattr(t, "unidade", None), "secretaria", None), "nome", "—")},
                ],
                "can_edit": False,
                "edit_url": "",
            })
        return rows

    def get_extra_filters_html(self, *, ano=None, **kwargs):
        qs = self.get_base_queryset()
        anos = list(qs.order_by("-ano_letivo").values_list("ano_letivo", flat=True).distinct())[:12]
        if not anos:
            return ""
        opts = []
        sel = "selected" if not ano else ""
        opts.append(f'<option value="" {sel}>Todos os anos</option>')
        for a in anos:
            s = "selected" if str(ano) == str(a) else ""
            opts.append(f'<option value="{a}" {s}>{a}</option>')
        return f'''
<div class="filter-bar__field">
  <label class="small">Ano letivo</label>
  <select name="ano">
    {''.join(opts)}
  </select>
</div>
'''.strip()
