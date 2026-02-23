from __future__ import annotations

from django.db.models import Q
from django.urls import reverse
from django.utils.html import escape

from apps.core.rbac import can
from apps.core.exports import export_csv, export_pdf_table

from .base_views import BaseAlunoListView, BaseAlunoCreateView, BaseAlunoUpdateView, BaseAlunoDetailView
from .forms import RecursoNEEForm
from .models import RecursoNEE


class RecursoListView(BaseAlunoListView):
    template_name = "nee/recurso_list.html"
    paginate_by = 20
    manage_perm = "nee.manage"

    def get_base_queryset(self):
        aluno = self.get_aluno()
        return RecursoNEE.objects.filter(aluno=aluno).order_by("nome")

    def apply_search(self, qs, q: str, **kwargs):
        if q:
            qs = qs.filter(Q(nome__icontains=q) | Q(observacao__icontains=q) | Q(status__icontains=q))
        return qs

    def get_actions(self, q: str = "", **kwargs):
        actions = super().get_actions(q=q, **kwargs)

        aluno = self.get_aluno()
        if can(self.request.user, "nee.manage"):
            actions.append({
                "label": "Novo recurso",
                "url": reverse("nee:recurso_create", args=[aluno.pk]),
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
            {"label": "Nome"},
            {"label": "Status", "width": "180px"},
        ]

    def get_rows(self, request, page_obj):
        rows = []
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
        export = request.GET.get("export")
        if export in ("csv", "pdf"):
            qs = self.get_queryset(request)
            if q:
                qs = self.apply_search(qs, q)

            headers = ["Nome", "Status", "Observação"]
            rows = [[r.nome, r.get_status_display(), r.observacao or ""] for r in qs]

            aluno = self.get_aluno()
            if export == "csv":
                return export_csv(f"nee_recursos_{aluno.pk}.csv", headers, rows)

            return export_pdf_table(
                request,
                filename=f"nee_recursos_{aluno.pk}.pdf",
                title=f"NEE — Recursos ({aluno.nome})",
                subtitle="Recursos / adaptações",
                headers=headers,
                rows=rows,
                filtros=(f"Busca: {q}" if q else ""),
            )

        return super().get(request, *args, **kwargs)


class RecursoCreateView(BaseAlunoCreateView):
    template_name = "nee/recurso_form.html"
    form_class = RecursoNEEForm
    title = "Novo recurso"
    subtitle = "Cadastrar recurso/adaptação"
    manage_perm = "nee.manage"

    back_url_name = "nee:aluno_recursos"
    success_url_name = "nee:aluno_recursos"


class RecursoUpdateView(BaseAlunoUpdateView):
    template_name = "nee/recurso_form.html"
    form_class = RecursoNEEForm
    model = RecursoNEE
    title = "Editar recurso"
    subtitle = "Atualizar recurso/adaptação"
    manage_perm = "nee.manage"

    success_url_name = "nee:aluno_recursos"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        return [{
            "label": "Voltar",
            "url": reverse("nee:recurso_detail", args=[obj.pk]),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }]


class RecursoDetailView(BaseAlunoDetailView):
    template_name = "nee/recurso_detail.html"
    model = RecursoNEE
    title = "Recurso"
    subtitle = "Detalhes do recurso"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        actions = [
            {
                "label": "Voltar",
                "url": reverse("nee:aluno_recursos", args=[obj.aluno_id]),
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
                "url": reverse("nee:recurso_update", args=[obj.pk]),
                "icon": "fa-solid fa-pen",
                "variant": "btn-primary",
            })
        return actions

    def get_fields(self, request, obj):
        return [
            ("Aluno", str(obj.aluno)),
            ("Nome", obj.nome),
            ("Status", obj.get_status_display()),
            ("Observação", obj.observacao or "—"),
        ]
