from __future__ import annotations

from django.db.models import Q
from django.urls import reverse
from django.utils.html import escape

from apps.core.rbac import can, scope_filter_alunos
from apps.core.views_gepub import BaseCreateViewGepub, BaseDetailViewGepub, BaseListViewGepub, BaseUpdateViewGepub
from apps.core.exports import export_csv, export_pdf_table
from apps.educacao.models import Aluno

from .forms import AlunoNecessidadeForm
from .models import AlunoNecessidade


class AlunoNecessidadeListView(BaseListViewGepub):
    template_name = "nee/aluno_necessidade_list.html"
    paginate_by = 20
    manage_perm = "nee.manage"

    def get_base_queryset(self):
        aluno_id = int(self.kwargs["aluno_id"])
        # escopo do aluno
        qs_aluno = scope_filter_alunos(self.request.user, Aluno.objects.filter(id=aluno_id))
        aluno = qs_aluno.first()
        if not aluno:
            return AlunoNecessidade.objects.none()
        self._aluno = aluno
        return AlunoNecessidade.objects.select_related("tipo").filter(aluno_id=aluno_id).order_by("-criado_em", "-id")

    def apply_search(self, qs, q: str, **kwargs):
        if q:
            qs = qs.filter(Q(tipo__nome__icontains=q) | Q(cid__icontains=q) | Q(observacao__icontains=q))
        return qs

    def get_actions(self, q: str = "", **kwargs):
        aluno = getattr(self, "_aluno", None)
        actions = [
            {"label": "Voltar", "url": reverse("nee:aluno_search"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        ]
        if aluno:
            actions.append({"label": "Abrir aluno", "url": reverse("educacao:aluno_detail", args=[aluno.pk]), "icon": "fa-solid fa-user", "variant": "btn--ghost"})
        if can(self.request.user, "nee.manage") and aluno:
            actions.append({"label": "Nova necessidade", "url": reverse("nee:aluno_necessidade_create", args=[aluno.pk]), "icon": "fa-solid fa-plus", "variant": "btn-primary"})
        actions.append({"label": "Exportar CSV", "url": f"{self.request.path}?q={escape(q)}&export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"})
        actions.append({"label": "Exportar PDF", "url": f"{self.request.path}?q={escape(q)}&export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"})
        return actions

    def get_headers(self, *args, **kwargs):
        return [
            {"label": "Tipo"},
            {"label": "CID", "width": "140px"},
            {"label": "Ativo", "width": "120px"},
            {"label": "Criado", "width": "140px"},
        ]

    def get_rows(self, request, page_obj):
        rows=[]
        for n in page_obj.object_list:
            rows.append({
                "cells": [
                    {"text": n.tipo.nome, "url": reverse("nee:aluno_necessidade_detail", args=[n.pk])},
                    {"text": n.cid or "—"},
                    {"text": "Sim" if n.ativo else "Não"},
                    {"text": n.criado_em.strftime("%d/%m/%Y") if getattr(n, "criado_em", None) else "—"},
                ],
                "can_edit": can(request.user, "nee.manage"),
                "edit_url": reverse("nee:aluno_necessidade_update", args=[n.pk]),
            })
        return rows

    def get(self, request, *args, **kwargs):
        q = (request.GET.get(self.search_param) or "").strip()
        if request.GET.get("export") in ("csv","pdf"):
            qs = self.get_queryset(request)
            if q:
                qs = self.apply_search(qs, q)
            headers = ["Tipo", "CID", "Ativo", "Criado em"]
            rows = []
            for n in qs:
                rows.append([
                    n.tipo.nome,
                    n.cid or "",
                    "Sim" if n.ativo else "Não",
                    getattr(n, "criado_em", None).strftime("%d/%m/%Y %H:%M") if getattr(n, "criado_em", None) else "",
                ])
            if request.GET.get("export") == "csv":
                return export_csv("nee_necessidades.csv", headers, rows)
            aluno = getattr(self, "_aluno", None)
            title = f"NEE — Necessidades ({aluno.nome})" if aluno else "NEE — Necessidades"
            return export_pdf_table(request, filename="nee_necessidades.pdf", title=title, headers=headers, rows=rows, subtitle="Necessidades por aluno", filtros=(f"Busca: {q}" if q else ""))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, request, **kwargs):
        ctx = super().get_context_data(request, **kwargs)
        aluno = getattr(self, "_aluno", None)
        if aluno:
            ctx["aluno"] = aluno
            ctx["page_title"] = "Necessidades"
            ctx["page_subtitle"] = aluno.nome
        return ctx


class AlunoNecessidadeCreateView(BaseCreateViewGepub):
    template_name = "nee/aluno_necessidade_form.html"
    form_class = AlunoNecessidadeForm
    title = "Nova necessidade"
    subtitle = "Vincular tipo ao aluno"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", **kwargs):
        aluno_id = int(self.kwargs["aluno_id"])
        return [
            {"label": "Voltar", "url": reverse("nee:aluno_necessidade_list", args=[aluno_id]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        ]

    def get_form(self, request, *args, **kwargs):
        aluno_id = int(self.kwargs["aluno_id"])
        form = super().get_form(request, *args, **kwargs)
        # trava aluno no form
        form.fields["aluno"].initial = aluno_id
        form.fields["aluno"].widget = form.fields["aluno"].hidden_widget()
        return form

    def get_success_url(self, request, obj=None) -> str:
        return reverse("nee:aluno_necessidade_list", args=[obj.aluno_id])


class AlunoNecessidadeUpdateView(BaseUpdateViewGepub):
    template_name = "nee/aluno_necessidade_form.html"
    form_class = AlunoNecessidadeForm
    model = AlunoNecessidade
    title = "Editar necessidade"
    subtitle = "Atualizar vínculo do aluno"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        return [
            {"label": "Voltar", "url": reverse("nee:aluno_necessidade_detail", args=[obj.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        ]

    def get_success_url(self, request, obj=None) -> str:
        return reverse("nee:aluno_necessidade_list", args=[obj.aluno_id])


class AlunoNecessidadeDetailView(BaseDetailViewGepub):
    template_name = "nee/aluno_necessidade_detail.html"
    model = AlunoNecessidade
    title = "Necessidade"
    subtitle = "Detalhes do vínculo"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        actions = [
            {"label": "Voltar", "url": reverse("nee:aluno_necessidade_list", args=[obj.aluno_id]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Abrir aluno", "url": reverse("educacao:aluno_detail", args=[obj.aluno_id]), "icon": "fa-solid fa-user", "variant": "btn--ghost"},
        ]
        if can(self.request.user, "nee.manage"):
            actions.append({"label": "Editar", "url": reverse("nee:aluno_necessidade_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})
        return actions

    def get_fields(self, request, obj):
        return [
            ("Aluno", str(obj.aluno)),
            ("Tipo", obj.tipo.nome),
            ("CID", obj.cid or "—"),
            ("Ativo", "Sim" if obj.ativo else "Não"),
            ("Criado em", obj.criado_em.strftime("%d/%m/%Y %H:%M") if getattr(obj, "criado_em", None) else "—"),
            ("Observação", obj.observacao or "—"),
        ]
