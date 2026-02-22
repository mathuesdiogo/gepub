from __future__ import annotations

from django.db.models import Q
from django.urls import reverse
from django.utils.html import escape

from apps.core.rbac import can
from apps.core.views_gepub import BaseCreateViewGepub, BaseDetailViewGepub, BaseListViewGepub, BaseUpdateViewGepub
from apps.core.exports import export_csv, export_pdf_table

from .forms import RecursoNEEForm
from .models import RecursoNEE
from .utils import get_scoped_aluno


class RecursoListView(BaseListViewGepub):
    template_name = "nee/recurso_list.html"
    paginate_by = 20
    manage_perm = "nee.manage"

    def get_base_queryset(self):
        aluno = get_scoped_aluno(self.request.user, int(self.kwargs["aluno_id"]))
        self._aluno = aluno
        return RecursoNEE.objects.filter(aluno=aluno).order_by("nome")

    def apply_search(self, qs, q: str, **kwargs):
        if q:
            qs = qs.filter(Q(nome__icontains=q) | Q(observacao__icontains=q) | Q(status__icontains=q))
        return qs

    def get_actions(self, q: str = "", **kwargs):
        aluno = getattr(self, "_aluno", None)
        actions = [{"label": "Voltar", "url": reverse("educacao:aluno_detail", args=[aluno.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
        if can(self.request.user, "nee.manage"):
            actions.append({"label": "Novo recurso", "url": reverse("nee:recurso_create", args=[aluno.pk]), "icon": "fa-solid fa-plus", "variant": "btn-primary"})
        actions.append({"label": "Exportar CSV", "url": f"{self.request.path}?q={escape(q)}&export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"})
        actions.append({"label": "Exportar PDF", "url": f"{self.request.path}?q={escape(q)}&export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"})
        return actions

    def get_headers(self, *args, **kwargs):
        return [
            {"label": "Nome"},
            {"label": "Status", "width": "180px"},
        ]

    def get_rows(self, request, page_obj):
        rows=[]
        for r in page_obj.object_list:
            rows.append({
                "cells": [
                    {"text": r.nome, "url": reverse("nee:recurso_detail", args=[r.pk])},
                    {"text": r.get_status_display()},
                ],
                "can_edit": can(request.user, "nee.manage"),
                "edit_url": reverse("nee:recurso_update", args=[r.pk]),
            })
        return rows

    def get(self, request, *args, **kwargs):
        q = (request.GET.get(self.search_param) or "").strip()
        if request.GET.get("export") in ("csv","pdf"):
            qs = self.get_queryset(request)
            if q:
                qs = self.apply_search(qs, q)
            headers = ["Nome", "Status"]
            rows = [[r.nome, r.get_status_display()] for r in qs]
            if request.GET.get("export") == "csv":
                return export_csv("nee_recursos.csv", headers, rows)
            aluno = getattr(self, "_aluno", None)
            return export_pdf_table(request, filename="nee_recursos.pdf", title=f"NEE — Recursos ({aluno.nome})", headers=headers, rows=rows, subtitle="Recursos por aluno", filtros=(f"Busca: {q}" if q else ""))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, request, **kwargs):
        ctx = super().get_context_data(request, **kwargs)
        ctx["aluno"] = getattr(self, "_aluno", None)
        return ctx


class RecursoCreateView(BaseCreateViewGepub):
    template_name = "nee/recurso_form.html"
    form_class = RecursoNEEForm
    title = "Novo recurso"
    subtitle = "Cadastrar recurso/adaptação"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", **kwargs):
        aluno_id = int(self.kwargs["aluno_id"])
        return [{"label": "Voltar", "url": reverse("nee:recurso_list", args=[aluno_id]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]

    def get_form(self, request, *args, **kwargs):
        aluno_id = int(self.kwargs["aluno_id"])
        form = super().get_form(request, *args, **kwargs)
        form.fields["aluno"].initial = aluno_id
        form.fields["aluno"].widget = form.fields["aluno"].hidden_widget()
        return form

    def get_success_url(self, request, obj=None) -> str:
        return reverse("nee:recurso_list", args=[obj.aluno_id])


class RecursoUpdateView(BaseUpdateViewGepub):
    template_name = "nee/recurso_form.html"
    form_class = RecursoNEEForm
    model = RecursoNEE
    title = "Editar recurso"
    subtitle = "Atualizar recurso/adaptação"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        return [{"label": "Voltar", "url": reverse("nee:recurso_detail", args=[obj.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]

    def get_success_url(self, request, obj=None) -> str:
        return reverse("nee:recurso_list", args=[obj.aluno_id])


class RecursoDetailView(BaseDetailViewGepub):
    template_name = "nee/recurso_detail.html"
    model = RecursoNEE
    title = "Recurso"
    subtitle = "Detalhes do recurso"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        actions = [
            {"label": "Voltar", "url": reverse("nee:recurso_list", args=[obj.aluno_id]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Abrir aluno", "url": reverse("educacao:aluno_detail", args=[obj.aluno_id]), "icon": "fa-solid fa-user", "variant": "btn--ghost"},
        ]
        if can(self.request.user, "nee.manage"):
            actions.append({"label": "Editar", "url": reverse("nee:recurso_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})
        return actions

    def get_fields(self, request, obj):
        return [
            ("Aluno", str(obj.aluno)),
            ("Nome", obj.nome),
            ("Status", obj.get_status_display()),
            ("Observação", obj.observacao or "—"),
        ]
