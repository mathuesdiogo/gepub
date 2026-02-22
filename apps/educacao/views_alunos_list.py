from __future__ import annotations

from django.db.models import Q
from django.urls import reverse
from django.utils.html import escape

from apps.core.rbac import can, scope_filter_alunos
from apps.core.views_gepub import BaseListViewGepub
from apps.core.exports import export_csv, export_pdf_table

from .models import Aluno


class AlunoListView(BaseListViewGepub):
    template_name = "educacao/aluno_list.html"
    url_name = "educacao:aluno_list"

    page_title = "Alunos"
    page_subtitle = "Cadastro e consulta de alunos"

    paginate_by = 10
    autocomplete_url_name = "educacao:api_alunos_suggest"

    search_fields = ["nome", "cpf", "nis", "nome_mae"]

    def get_base_queryset(self):
        qs = Aluno.objects.only("id", "nome", "cpf", "nis", "nome_mae", "ativo")
        return scope_filter_alunos(self.request.user, qs)

    def _flag_only_nee(self) -> bool:
        v = (self.request.GET.get("nee") or "").strip().lower()
        return v in ("1", "true", "on", "yes", "sim")

    def apply_search(self, qs, q: str, **kwargs):
        if q:
            qs = qs.filter(
                Q(nome__icontains=q)
                | Q(cpf__icontains=q)
                | Q(nis__icontains=q)
                | Q(nome_mae__icontains=q)
            )
        # Filtro extra: somente alunos com NEE
        if self._flag_only_nee():
            qs = qs.filter(necessidades_nee__isnull=False).distinct()
        return qs

    def get(self, request, *args, **kwargs):
        # export mantém o comportamento atual (CSV/PDF) + respeita filtro NEE
        q = (request.GET.get("q") or "").strip()
        export = (request.GET.get("export") or "").strip().lower()
        qs = self.apply_search(self.get_base_queryset(), q)

        if export in ("csv", "pdf"):
            items = list(qs.order_by("nome").values_list("nome", "cpf", "nis", "ativo"))
            headers_export = ["Nome", "CPF", "NIS", "Ativo"]
            rows_export = [
                [nome or "", cpf or "", nis or "", "Sim" if ativo else "Não"]
                for (nome, cpf, nis, ativo) in items
            ]

            if export == "csv":
                return export_csv("alunos.csv", headers_export, rows_export)

            filtros = f"Busca={q or '-'}"
            if self._flag_only_nee():
                filtros += " | Somente NEE=Sim"
            return export_pdf_table(
                request,
                filename="alunos.pdf",
                title="Relatório — Alunos",
                headers=headers_export,
                rows=rows_export,
                filtros=filtros,
            )

        return super().get(request, *args, **kwargs)

    def get_actions(self, q: str = "", **kwargs):
        can_edu_manage = can(self.request.user, "educacao.manage")

        base_parts = []
        if q:
            base_parts.append(f"q={escape(q)}")
        if self._flag_only_nee():
            base_parts.append("nee=1")
        base_q = "&".join(base_parts)

        def _u(extra: str) -> str:
            if not base_q:
                return f"?{extra}"
            return f"?{base_q}&{extra}"

        actions = [
            {"label": "Exportar CSV", "url": _u("export=csv"), "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
            {"label": "Exportar PDF", "url": _u("export=pdf"), "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
        ]

        if can_edu_manage:
            actions.append({"label": "Novo Aluno", "url": reverse("educacao:aluno_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})
        return actions

    def get_extra_filters_html(self, request, **kwargs) -> str:
        checked = "checked" if self._flag_only_nee() else ""
        # HTML simples e compatível com filter_bar (renderiza extra_filters)
        return (
            '<label class="check" style="display:inline-flex;gap:8px;align-items:center;">'
            f'<input type="checkbox" name="nee" value="1" {checked} onchange="this.form.submit()">'
            '<span>Somente com NEE</span>'
            '</label>'
        )

    def get_headers(self, **kwargs):
        return [
            {"label": "Nome"},
            {"label": "CPF", "width": "160px"},
            {"label": "NIS", "width": "160px"},
            {"label": "Ativo", "width": "140px"},
        ]

    def get_rows(self, objs, **kwargs):
        can_edu_manage = can(self.request.user, "educacao.manage")
        rows = []
        for a in objs:
            rows.append({
                "cells": [
                    {"text": a.nome, "url": reverse("educacao:aluno_detail", args=[a.pk])},
                    {"text": a.cpf or "—"},
                    {"text": a.nis or "—"},
                    {"text": "Sim" if a.ativo else "Não"},
                ],
                "can_edit": bool(can_edu_manage and a.pk),
                "edit_url": reverse("educacao:aluno_update", args=[a.pk]) if a.pk else "",
            })
        return rows
