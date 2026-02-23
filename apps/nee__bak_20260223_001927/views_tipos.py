from __future__ import annotations

from django.db.models import Q
from django.urls import reverse
from django.utils.html import escape

from apps.core.rbac import can
from apps.core.views_gepub import BaseCreateViewGepub, BaseDetailViewGepub, BaseListViewGepub, BaseUpdateViewGepub
from apps.core.exports import export_csv, export_pdf_table

from .forms import TipoNecessidadeForm
from .models import TipoNecessidade


class TipoListView(BaseListViewGepub):
    template_name = "nee/tipo_list.html"
    url_name = "nee:tipo_list"

    page_title = "Tipos de necessidade"
    page_subtitle = "Catálogo para classificação NEE"

    paginate_by = 20
    manage_perm = "nee.manage"
    back_url_name = "nee:index"

    def get_base_queryset(self):
        return TipoNecessidade.objects.all().order_by("nome")

    def apply_search(self, qs, q: str, **kwargs):
        if q:
            qs = qs.filter(Q(nome__icontains=q))
        return qs

    def get_actions(self, q: str = "", **kwargs):
        actions = [
            {"label": "Voltar", "url": reverse("nee:index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        ]
        if can(self.request.user, "nee.manage"):
            actions.append({"label": "Novo tipo", "url": reverse("nee:tipo_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})
        # exports
        if self.request.GET.get("export") == "csv":
            pass
        actions.append({"label": "Exportar CSV", "url": f"{reverse('nee:tipo_list')}?q={escape(q)}&export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"})
        actions.append({"label": "Exportar PDF", "url": f"{reverse('nee:tipo_list')}?q={escape(q)}&export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"})
        return actions

    def get_headers(self, *args, **kwargs):
        return [
            {"label": "Nome"},
            {"label": "Ativo", "width": "140px"},
        ]

    def get_rows(self, request, page_obj):
        rows=[]
        for t in page_obj.object_list:
            rows.append({
                "cells": [
                    {"text": t.nome, "url": reverse("nee:tipo_detail", args=[t.pk])},
                    {"text": "Sim" if t.ativo else "Não"},
                ],
                "can_edit": can(request.user, "nee.manage"),
                "edit_url": reverse("nee:tipo_update", args=[t.pk]),
            })
        return rows

    def get(self, request, *args, **kwargs):
        # export hook before render
        q = (request.GET.get(self.search_param) or "").strip()
        if request.GET.get("export") in ("csv","pdf"):
            qs = self.get_queryset(request)
            if q:
                qs = self.apply_search(qs, q)
            headers = ["Nome", "Ativo"]
            rows = [[t.nome, "Sim" if t.ativo else "Não"] for t in qs]
            if request.GET.get("export") == "csv":
                return export_csv("nee_tipos.csv", headers, rows)
            return export_pdf_table(request, filename="nee_tipos.pdf", title="NEE — Tipos de necessidade", headers=headers, rows=rows, subtitle="Catálogo de tipos", filtros=(f"Busca: {q}" if q else ""))
        return super().get(request, *args, **kwargs)


class TipoCreateView(BaseCreateViewGepub):
    template_name = "nee/tipo_form.html"
    form_class = TipoNecessidadeForm
    title = "Novo tipo"
    subtitle = "Cadastrar tipo de necessidade"
    manage_perm = "nee.manage"
    back_url_name = "nee:tipo_list"

    def get_actions(self, q: str = "", **kwargs):
        return [
            {"label": "Voltar", "url": reverse("nee:tipo_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        ]


class TipoUpdateView(BaseUpdateViewGepub):
    template_name = "nee/tipo_form.html"
    form_class = TipoNecessidadeForm
    model = TipoNecessidade
    title = "Editar tipo"
    subtitle = "Atualizar tipo de necessidade"
    manage_perm = "nee.manage"
    back_url_name = "nee:tipo_list"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        return [
            {"label": "Voltar", "url": reverse("nee:tipo_detail", args=[obj.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        ]


class TipoDetailView(BaseDetailViewGepub):
    template_name = "nee/tipo_detail.html"
    model = TipoNecessidade
    title = "Tipo"
    subtitle = "Detalhes do tipo"
    manage_perm = "nee.manage"
    back_url_name = "nee:tipo_list"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        actions = [
            {"label": "Voltar", "url": reverse("nee:tipo_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        ]
        if can(self.request.user, "nee.manage"):
            actions.append({"label": "Editar", "url": reverse("nee:tipo_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})
        return actions

    def get_fields(self, request, obj):
        return [
            ("Nome", obj.nome),
            ("Ativo", "Sim" if obj.ativo else "Não"),
        ]
