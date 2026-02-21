from __future__ import annotations

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.core.rbac import can
from apps.core.views_gepub import BaseListViewGepub

from .models_periodos import PeriodoLetivo


class PeriodoListView(BaseListViewGepub):
    template_name = "educacao/periodo_list.html"
    url_name = "educacao:periodo_list"

    page_title = "Períodos Letivos"
    page_subtitle = "Bimestres/Trimestres/Semestres"

    paginate_by = 20
    default_ano = timezone.now().year

    def get_base_queryset(self):
        return PeriodoLetivo.objects.all().order_by("-ano_letivo", "tipo", "numero")

    def apply_ano(self, qs, ano, **kwargs):
        if ano:
            return qs.filter(ano_letivo=int(ano))
        return qs

    def apply_search(self, qs, q: str, **kwargs):
        if not q:
            return qs
        return qs.filter(Q(tipo__icontains=q) | Q(numero__icontains=q))

    def get_actions(self, **kwargs):
        actions = []
        if can(self.request.user, "educacao.manage"):
            actions.append({
                "label": "Gerar Bimestres",
                "url": reverse("educacao:periodo_gerar_bimestres"),
                "icon": "fa-solid fa-wand-magic-sparkles",
                "variant": "btn--ghost",
            })
            actions.append({
                "label": "Novo Período",
                "url": reverse("educacao:periodo_create"),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            })
        return actions

    def get_headers(self, **kwargs):
        return [
            {"label": "Ano", "width": "110px"},
            {"label": "Tipo", "width": "170px"},
            {"label": "Número", "width": "110px"},
            {"label": "Início", "width": "140px"},
            {"label": "Fim", "width": "140px"},
            {"label": "Ativo", "width": "110px"},
        ]

    def get_rows(self, objs, **kwargs):
        can_edit = bool(can(self.request.user, "educacao.manage"))
        rows = []
        for p in objs:
            ativo_html = '<span class="badge badge--success">Sim</span>' if p.ativo else '<span class="badge badge--muted">Não</span>'
            rows.append({
                "cells": [
                    {"text": str(p.ano_letivo)},
                    {"text": p.get_tipo_display() if hasattr(p, "get_tipo_display") else (p.tipo or "—")},
                    {"text": str(p.numero)},
                    {"text": p.inicio.strftime("%d/%m/%Y") if p.inicio else "—"},
                    {"text": p.fim.strftime("%d/%m/%Y") if p.fim else "—"},
                    {"html": ativo_html, "safe": True},
                ],
                "can_edit": can_edit,
                "edit_url": reverse("educacao:periodo_update", args=[p.pk]) if can_edit else "",
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
