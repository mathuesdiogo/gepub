from __future__ import annotations

from django.db.models import Q
from django.urls import reverse
from django.utils.html import escape

from apps.core.rbac import can
from apps.core.views_gepub import BaseCreateViewGepub, BaseDetailViewGepub, BaseListViewGepub, BaseUpdateViewGepub
from apps.core.exports import export_csv, export_pdf_table

from .forms import LaudoNEEForm
from .models import LaudoNEE
from .utils import get_scoped_aluno


class LaudoListView(BaseListViewGepub):
    template_name = "nee/laudo_list.html"
    paginate_by = 20
    manage_perm = "nee.manage"

    def get_base_queryset(self):
        aluno = get_scoped_aluno(self.request.user, int(self.kwargs["aluno_id"]))
        self._aluno = aluno
        return LaudoNEE.objects.filter(aluno=aluno).order_by("-data_emissao", "-id")

    def apply_search(self, qs, q: str, **kwargs):
        if q:
            qs = qs.filter(Q(numero__icontains=q) | Q(profissional__icontains=q) | Q(texto__icontains=q))
        return qs

    def get_actions(self, q: str = "", **kwargs):
        aluno = getattr(self, "_aluno", None)
        actions = [
            {"label": "Voltar", "url": reverse("educacao:aluno_detail", args=[aluno.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        ]
        if can(self.request.user, "nee.manage"):
            actions.append({"label": "Novo laudo", "url": reverse("nee:laudo_create", args=[aluno.pk]), "icon": "fa-solid fa-plus", "variant": "btn-primary"})
        actions.append({"label": "Exportar CSV", "url": f"{self.request.path}?q={escape(q)}&export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"})
        actions.append({"label": "Exportar PDF", "url": f"{self.request.path}?q={escape(q)}&export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"})
        return actions

    def get_headers(self, *args, **kwargs):
        return [
            {"label": "Emissão", "width": "140px"},
            {"label": "Validade", "width": "140px"},
            {"label": "Número", "width": "180px"},
            {"label": "Profissional"},
        ]

    def get_rows(self, request, page_obj):
        rows=[]
        for l in page_obj.object_list:
            rows.append({
                "cells": [
                    {"text": l.data_emissao.strftime("%d/%m/%Y"), "url": reverse("nee:laudo_detail", args=[l.pk])},
                    {"text": l.validade.strftime("%d/%m/%Y") if l.validade else "—"},
                    {"text": l.numero or "—"},
                    {"text": l.profissional or "—"},
                ],
                "can_edit": can(request.user, "nee.manage"),
                "edit_url": reverse("nee:laudo_update", args=[l.pk]),
            })
        return rows

    def get(self, request, *args, **kwargs):
        q = (request.GET.get(self.search_param) or "").strip()
        if request.GET.get("export") in ("csv","pdf"):
            qs = self.get_queryset(request)
            if q:
                qs = self.apply_search(qs, q)
            headers = ["Emissão", "Validade", "Número", "Profissional"]
            rows = []
            for l in qs:
                rows.append([
                    l.data_emissao.strftime("%d/%m/%Y"),
                    l.validade.strftime("%d/%m/%Y") if l.validade else "",
                    l.numero or "",
                    l.profissional or "",
                ])
            if request.GET.get("export") == "csv":
                return export_csv("nee_laudos.csv", headers, rows)
            aluno = getattr(self, "_aluno", None)
            return export_pdf_table(request, filename="nee_laudos.pdf", title=f"NEE — Laudos ({aluno.nome})", headers=headers, rows=rows, subtitle="Laudos por aluno", filtros=(f"Busca: {q}" if q else ""))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, request, **kwargs):
        ctx = super().get_context_data(request, **kwargs)
        aluno = getattr(self, "_aluno", None)
        ctx["aluno"] = aluno
        return ctx


class LaudoCreateView(BaseCreateViewGepub):
    template_name = "nee/laudo_form.html"
    form_class = LaudoNEEForm
    title = "Novo laudo"
    subtitle = "Cadastrar laudo do aluno"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", **kwargs):
        aluno_id = int(self.kwargs["aluno_id"])
        return [{"label": "Voltar", "url": reverse("nee:laudo_list", args=[aluno_id]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]

    def get_form(self, request, *args, **kwargs):
        aluno_id = int(self.kwargs["aluno_id"])
        form = super().get_form(request, *args, **kwargs)
        form.fields["aluno"].initial = aluno_id
        form.fields["aluno"].widget = form.fields["aluno"].hidden_widget()
        return form

    def get_success_url(self, request, obj=None) -> str:
        return reverse("nee:laudo_list", args=[obj.aluno_id])


class LaudoUpdateView(BaseUpdateViewGepub):
    template_name = "nee/laudo_form.html"
    form_class = LaudoNEEForm
    model = LaudoNEE
    title = "Editar laudo"
    subtitle = "Atualizar dados do laudo"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        return [{"label": "Voltar", "url": reverse("nee:laudo_detail", args=[obj.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]

    def get_success_url(self, request, obj=None) -> str:
        return reverse("nee:laudo_list", args=[obj.aluno_id])


class LaudoDetailView(BaseDetailViewGepub):
    template_name = "nee/laudo_detail.html"
    model = LaudoNEE
    title = "Laudo"
    subtitle = "Detalhes do laudo"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        actions = [
            {"label": "Voltar", "url": reverse("nee:laudo_list", args=[obj.aluno_id]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Abrir aluno", "url": reverse("educacao:aluno_detail", args=[obj.aluno_id]), "icon": "fa-solid fa-user", "variant": "btn--ghost"},
        ]
        if can(self.request.user, "nee.manage"):
            actions.append({"label": "Editar", "url": reverse("nee:laudo_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})
        return actions

    def get_fields(self, request, obj):
        return [
            ("Aluno", str(obj.aluno)),
            ("Número", obj.numero or "—"),
            ("Emissão", obj.data_emissao.strftime("%d/%m/%Y")),
            ("Validade", obj.validade.strftime("%d/%m/%Y") if obj.validade else "—"),
            ("Profissional", obj.profissional or "—"),
            ("Texto", obj.texto or "—"),
            ("Arquivo", obj.documento.url if obj.documento else "—"),
        ]
