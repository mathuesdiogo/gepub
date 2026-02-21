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

    def apply_search(self, qs, q: str, **kwargs):
        if not q:
            return qs
        return qs.filter(
            Q(nome__icontains=q)
            | Q(cpf__icontains=q)
            | Q(nis__icontains=q)
            | Q(nome_mae__icontains=q)
        )

    def get(self, request, *args, **kwargs):
        # export mantém o comportamento atual (CSV/PDF)
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

        base_q = f"q={escape(q)}" if q else ""
        actions = [
            {
                "label": "Exportar CSV",
                "url": f"?{base_q + ('&' if base_q else '')}export=csv",
                "icon": "fa-solid fa-file-csv",
                "variant": "btn--ghost",
            },
            {
                "label": "Exportar PDF",
                "url": f"?{base_q + ('&' if base_q else '')}export=pdf",
                "icon": "fa-solid fa-file-pdf",
                "variant": "btn--ghost",
            },
        ]

        if can_edu_manage:
            actions.append(
                {
                    "label": "Novo Aluno",
                    "url": reverse("educacao:aluno_create"),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            )

        return actions

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
            rows.append(
                {
                    "cells": [
                        {"text": a.nome, "url": reverse("educacao:aluno_detail", args=[a.pk])},
                        {"text": a.cpf or "—"},
                        {"text": a.nis or "—"},
                        {"text": "Sim" if a.ativo else "Não"},
                    ],
                    "can_edit": bool(can_edu_manage and a.pk),
                    "edit_url": reverse("educacao:aluno_update", args=[a.pk]) if a.pk else "",
                }
            )
        return rows
