from __future__ import annotations

from django.db.models import Q
from django.urls import reverse
from django.utils.html import escape

from apps.core.rbac import can
from apps.core.exports import export_csv, export_pdf_table

from .base_views import BaseAlunoListView, BaseAlunoCreateView, BaseAlunoUpdateView, BaseAlunoDetailView
from .forms import LaudoNEEForm
from .models import LaudoNEE


class LaudoListView(BaseAlunoListView):
    template_name = "nee/laudo_list.html"
    paginate_by = 20
    manage_perm = "nee.manage"

    def get_base_queryset(self):
        aluno = self.get_aluno()
        return LaudoNEE.objects.filter(aluno=aluno).order_by("-data_emissao", "-id")

    def apply_search(self, qs, q: str, **kwargs):
        if q:
            qs = qs.filter(
                Q(numero__icontains=q)
                | Q(profissional__icontains=q)
                | Q(texto__icontains=q)
            )
        return qs

    def get_actions(self, q: str = "", **kwargs):
        actions = super().get_actions(q=q, **kwargs)

        aluno = self.get_aluno()
        if can(self.request.user, "nee.manage"):
            actions.append({
                "label": "Novo laudo",
                "url": reverse("nee:laudo_create", args=[aluno.pk]),
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
            {"label": "Número", "width": "160px"},
            {"label": "Emissão", "width": "140px"},
            {"label": "Validade", "width": "140px"},
            {"label": "Profissional"},
        ]

    def get_rows(self, request, page_obj):
        rows = []
        for l in page_obj.object_list:
            rows.append({
                "cells": [
                    {"text": l.numero or "—", "url": reverse("nee:laudo_detail", args=[l.pk])},
                    {"text": l.data_emissao.strftime("%d/%m/%Y") if l.data_emissao else "—"},
                    {"text": l.validade.strftime("%d/%m/%Y") if l.validade else "—"},
                    {"text": l.profissional or "—"},
                ],
                "can_edit": can(request.user, "nee.manage"),
                "edit_url": reverse("nee:laudo_update", args=[l.pk]),
            })
        return rows

    def get(self, request, *args, **kwargs):
        q = (request.GET.get(self.search_param) or "").strip()
        export = request.GET.get("export")
        if export in ("csv", "pdf"):
            qs = self.get_queryset(request)
            if q:
                qs = self.apply_search(qs, q)

            headers = ["Número", "Emissão", "Validade", "Profissional"]
            rows = [[
                (l.numero or ""),
                (l.data_emissao.strftime("%d/%m/%Y") if l.data_emissao else ""),
                (l.validade.strftime("%d/%m/%Y") if l.validade else ""),
                (l.profissional or ""),
            ] for l in qs]

            aluno = self.get_aluno()
            if export == "csv":
                return export_csv(f"nee_laudos_{aluno.pk}.csv", headers, rows)

            return export_pdf_table(
                request,
                filename=f"nee_laudos_{aluno.pk}.pdf",
                title=f"NEE — Laudos ({aluno.nome})",
                subtitle="Laudos do aluno",
                headers=headers,
                rows=rows,
                filtros=(f"Busca: {q}" if q else ""),
            )

        return super().get(request, *args, **kwargs)


class LaudoCreateView(BaseAlunoCreateView):
    template_name = "nee/laudo_form.html"
    form_class = LaudoNEEForm
    title = "Novo laudo"
    subtitle = "Cadastrar laudo para o aluno"
    manage_perm = "nee.manage"

    back_url_name = "nee:aluno_laudos"
    success_url_name = "nee:aluno_laudos"


class LaudoUpdateView(BaseAlunoUpdateView):
    template_name = "nee/laudo_form.html"
    form_class = LaudoNEEForm
    model = LaudoNEE
    title = "Editar laudo"
    subtitle = "Atualizar laudo do aluno"
    manage_perm = "nee.manage"

    success_url_name = "nee:aluno_laudos"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        return [
            {
                "label": "Voltar",
                "url": reverse("nee:laudo_detail", args=[obj.pk]),
                "icon": "fa-solid fa-arrow-left",
                "variant": "btn--ghost",
            }
        ]


class LaudoDetailView(BaseAlunoDetailView):
    template_name = "nee/laudo_detail.html"
    model = LaudoNEE
    title = "Laudo"
    subtitle = "Detalhes do laudo"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        actions = [
            {
                "label": "Voltar",
                "url": reverse("nee:aluno_laudos", args=[obj.aluno_id]),
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
                "url": reverse("nee:laudo_update", args=[obj.pk]),
                "icon": "fa-solid fa-pen",
                "variant": "btn-primary",
            })
        return actions
