from __future__ import annotations

from django.db.models import Q
from django.urls import reverse
from django.utils.html import escape

from apps.core.rbac import can
from apps.core.exports import export_csv, export_pdf_table

from .base_views import BaseAlunoListView, BaseAlunoCreateView, BaseAlunoUpdateView, BaseAlunoDetailView
from .forms import AlunoNecessidadeForm
from .models import AlunoNecessidade


class AlunoNecessidadeListView(BaseAlunoListView):
    template_name = "nee/aluno_necessidade_list.html"
    paginate_by = 20
    manage_perm = "nee.manage"

    def get_base_queryset(self):
        aluno = self.get_aluno()
        return AlunoNecessidade.objects.filter(aluno=aluno).select_related("tipo").order_by("-criado_em", "-id")

    def apply_search(self, qs, q: str, **kwargs):
        if q:
            qs = qs.filter(Q(tipo__nome__icontains=q) | Q(cid__icontains=q) | Q(observacao__icontains=q))
        return qs

    def get_actions(self, q: str = "", **kwargs):
        actions = super().get_actions(q=q, **kwargs)

        aluno = self.get_aluno()
        if can(self.request.user, "nee.manage"):
            actions.append({
                "label": "Nova necessidade",
                "url": reverse("nee:necessidade_create", args=[aluno.pk]),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            })

        actions.append({
            "label": "Exportar CSV",
            "url": f"{self.request.path}?q={escape(q)}&export=csv",
            "icon": "fa-solid fa-file-csv",
            "variant": "btn--ghost",
        })
        actions.append({
            "label": "Exportar PDF",
            "url": f"{self.request.path}?q={escape(q)}&export=pdf",
            "icon": "fa-solid fa-file-pdf",
            "variant": "btn--ghost",
        })
        return actions

    def get_headers(self, *args, **kwargs):
        return [
            {"label": "Tipo"},
            {"label": "CID", "width": "140px"},
            {"label": "Ativo", "width": "120px"},
        ]

    def get_rows(self, request, page_obj):
        rows = []
        for n in page_obj.object_list:
            rows.append({
                "cells": [
                    {"text": str(n.tipo), "url": reverse("nee:necessidade_detail", args=[n.pk])},
                    {"text": n.cid or "—"},
                    {"text": "Sim" if n.ativo else "Não"},
                ],
                "can_edit": can(request.user, "nee.manage"),
                "edit_url": reverse("nee:necessidade_update", args=[n.pk]),
            })
        return rows

    def get(self, request, *args, **kwargs):
        q = (request.GET.get(self.search_param) or "").strip()
        export = request.GET.get("export")
        if export in ("csv", "pdf"):
            qs = self.get_queryset(request)
            if q:
                qs = self.apply_search(qs, q)

            headers = ["Tipo", "CID", "Ativo", "Observação"]
            rows = [[str(n.tipo), n.cid or "", "Sim" if n.ativo else "Não", n.observacao or ""] for n in qs]

            aluno = self.get_aluno()
            if export == "csv":
                return export_csv(f"nee_necessidades_{aluno.pk}.csv", headers, rows)

            return export_pdf_table(
                request,
                filename=f"nee_necessidades_{aluno.pk}.pdf",
                title=f"NEE — Necessidades ({aluno.nome})",
                subtitle="Necessidades do aluno",
                headers=headers,
                rows=rows,
                filtros=(f"Busca: {q}" if q else ""),
            )

        return super().get(request, *args, **kwargs)


class AlunoNecessidadeCreateView(BaseAlunoCreateView):
    template_name = "nee/aluno_necessidade_form.html"
    form_class = AlunoNecessidadeForm
    title = "Nova necessidade"
    subtitle = "Cadastrar necessidade do aluno"
    manage_perm = "nee.manage"

    back_url_name = "nee:aluno_necessidades"
    success_url_name = "nee:aluno_necessidades"


class AlunoNecessidadeUpdateView(BaseAlunoUpdateView):
    template_name = "nee/aluno_necessidade_form.html"
    form_class = AlunoNecessidadeForm
    model = AlunoNecessidade
    title = "Editar necessidade"
    subtitle = "Atualizar necessidade do aluno"
    manage_perm = "nee.manage"

    success_url_name = "nee:aluno_necessidades"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        return [{
            "label": "Voltar",
            "url": reverse("nee:necessidade_detail", args=[obj.pk]),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }]


class AlunoNecessidadeDetailView(BaseAlunoDetailView):
    template_name = "nee/aluno_necessidade_detail.html"
    model = AlunoNecessidade
    title = "Necessidade"
    subtitle = "Detalhes da necessidade"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        actions = [
            {
                "label": "Voltar",
                "url": reverse("nee:aluno_necessidades", args=[obj.aluno_id]),
                "icon": "fa-solid fa-arrow-left",
                "variant": "btn--ghost",
            },
            {
                "label": "Abrir aluno",
                "url": reverse("educacao:aluno_detail", args=[obj.aluno_id]),
                "icon": "fa-solid fa-user",
                "variant": "btn--ghost",
            },
        ]
        if can(self.request.user, "nee.manage"):
            actions.append({
                "label": "Editar",
                "url": reverse("nee:necessidade_update", args=[obj.pk]),
                "icon": "fa-solid fa-pen",
                "variant": "btn-primary",
            })
        return actions

    def get_fields(self, request, obj):
        return [
            ("Aluno", str(obj.aluno)),
            ("Tipo", str(obj.tipo)),
            ("CID", obj.cid or "—"),
            ("Ativo", "Sim" if obj.ativo else "Não"),
            ("Observação", obj.observacao or "—"),
            ("Criado em", obj.criado_em.strftime("%d/%m/%Y %H:%M") if obj.criado_em else "—"),
        ]
