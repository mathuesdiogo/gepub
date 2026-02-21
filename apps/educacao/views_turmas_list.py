from __future__ import annotations

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from apps.core.rbac import can, is_admin, scope_filter_turmas
from apps.core.views_gepub import BaseListViewGepub
from apps.core.exports import export_csv, export_pdf_table

from .models import Turma


class TurmaListView(BaseListViewGepub):
    template_name = "educacao/turma_list.html"
    url_name = "educacao:turma_list"

    page_title = "Turmas"
    page_subtitle = "Gerencie as turmas por unidade e ano letivo"

    paginate_by = 20
    autocomplete_url_name = "educacao:api_turmas_suggest"
    default_ano = timezone.now().year

    def get_base_queryset(self):
        qs = (
            Turma.objects.select_related(
                "unidade",
                "unidade__secretaria",
                "unidade__secretaria__municipio",
            )
            .only(
                "id",
                "nome",
                "ano_letivo",
                "turno",
                "ativo",
                "unidade_id",
                "unidade__nome",
                "unidade__secretaria__nome",
                "unidade__secretaria__municipio__nome",
            )
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
            | Q(unidade__secretaria__municipio__nome__icontains=q)
        )

    def get(self, request, *args, **kwargs):
        q = (request.GET.get("q") or "").strip()
        ano = (request.GET.get("ano") or "").strip()
        export = (request.GET.get("export") or "").strip().lower()

        qs = self.get_base_queryset()
        if ano.isdigit():
            qs = qs.filter(ano_letivo=int(ano))
        qs = self.apply_search(qs, q)

        if export in ("csv", "pdf"):
            turmas_export = qs.order_by("-ano_letivo", "nome")

            headers_export = ["Turma", "Ano", "Turno", "Unidade", "Secretaria", "Município", "Ativo"]
            rows_export = []
            for t in turmas_export:
                rows_export.append([
                    t.nome or "—",
                    str(t.ano_letivo or "—"),
                    t.get_turno_display() if hasattr(t, "get_turno_display") else (getattr(t, "turno", "") or "—"),
                    getattr(getattr(t, "unidade", None), "nome", "—"),
                    getattr(getattr(getattr(t, "unidade", None), "secretaria", None), "nome", "—"),
                    getattr(getattr(getattr(getattr(t, "unidade", None), "secretaria", None), "municipio", None), "nome", "—"),
                    "Sim" if getattr(t, "ativo", False) else "Não",
                ])

            if export == "csv":
                return export_csv("turmas.csv", headers_export, rows_export)

            filtros = f"Ano={ano or '-'} | Busca={q or '-'}"
            return export_pdf_table(
                request,
                filename="turmas.pdf",
                title="Relatório — Turmas",
                headers=headers_export,
                rows=rows_export,
                filtros=filtros,
            )

        return super().get(request, *args, **kwargs)

    def get_actions(self, q: str = "", ano=None, **kwargs):
        base_params = []
        if q:
            base_params.append(f"q={escape(q)}")
        if ano:
            base_params.append(f"ano={ano}")
        base_qs = "&".join(base_params)

        actions = [
            {
                "label": "Exportar CSV",
                "url": f"?{base_qs + ('&' if base_qs else '')}export=csv",
                "icon": "fa-solid fa-file-csv",
                "variant": "btn--ghost",
            },
            {
                "label": "Exportar PDF",
                "url": f"?{base_qs + ('&' if base_qs else '')}export=pdf",
                "icon": "fa-solid fa-file-pdf",
                "variant": "btn--ghost",
            },
        ]

        if can(self.request.user, "educacao.manage") or is_admin(self.request.user):
            actions.append({
                "label": "Nova Turma",
                "url": reverse("educacao:turma_create"),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            })
        return actions

    def get_headers(self, **kwargs):
        return [
            {"label": "Turma"},
            {"label": "Ano", "width": "110px"},
            {"label": "Turno", "width": "140px"},
            {"label": "Unidade"},
            {"label": "Secretaria"},
            {"label": "Município"},
            {"label": "Ativo", "width": "110px"},
        ]

    def get_rows(self, objs, **kwargs):
        can_edit_global = bool(can(self.request.user, "educacao.manage") or is_admin(self.request.user))
        rows = []
        for t in objs:
            unidade = getattr(t, "unidade", None)
            secretaria = getattr(unidade, "secretaria", None) if unidade else None
            municipio = getattr(secretaria, "municipio", None) if secretaria else None

            ativo = getattr(t, "ativo", False)
            ativo_html = '<span class="badge badge--success">Sim</span>' if ativo else '<span class="badge badge--muted">Não</span>'

            rows.append({
                "cells": [
                    {"text": t.nome, "url": reverse("educacao:turma_detail", args=[t.pk])},
                    {"text": str(getattr(t, "ano_letivo", "—"))},
                    {"text": t.get_turno_display() if hasattr(t, "get_turno_display") else (getattr(t, "turno", "") or "—")},
                    {"text": getattr(unidade, "nome", "—")},
                    {"text": getattr(secretaria, "nome", "—")},
                    {"text": getattr(municipio, "nome", "—")},
                    {"html": ativo_html, "safe": True},
                ],
                "can_edit": can_edit_global,
                "edit_url": reverse("educacao:turma_update", args=[t.pk]) if can_edit_global else "",
            })
        return rows

    def get_extra_filters_html(self, *, q: str = "", ano=None, **kwargs) -> str:
        # anos disponíveis (limitado) dentro do escopo
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
