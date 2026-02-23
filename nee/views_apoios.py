from __future__ import annotations

from django.db.models import Q
from django.urls import reverse
from django.utils.html import escape

from apps.core.rbac import can, scope_filter_matriculas
from apps.core.views_gepub import BaseCreateViewGepub, BaseDetailViewGepub, BaseListViewGepub, BaseUpdateViewGepub
from apps.core.exports import export_csv, export_pdf_table
from apps.educacao.models import Matricula

from .forms import ApoioMatriculaForm
from .models import ApoioMatricula
from .utils import get_scoped_aluno


class ApoioListView(BaseListViewGepub):
    template_name = "nee/apoio_list.html"
    paginate_by = 20
    manage_perm = "nee.manage"

    def get_base_queryset(self):
        aluno = get_scoped_aluno(self.request.user, int(self.kwargs["aluno_id"]))
        self._aluno = aluno
        matriculas = scope_filter_matriculas(self.request.user, Matricula.objects.filter(aluno=aluno))
        self._matricula_ids = list(matriculas.values_list("id", flat=True))
        return ApoioMatricula.objects.select_related("matricula", "matricula__turma", "matricula__turma__unidade").filter(matricula_id__in=self._matricula_ids).order_by("-criado_em","-id")

    def apply_search(self, qs, q: str, **kwargs):
        if q:
            qs = qs.filter(Q(descricao__icontains=q) | Q(observacao__icontains=q) | Q(tipo__icontains=q))
        return qs

    def get_actions(self, q: str = "", **kwargs):
        aluno = getattr(self, "_aluno", None)
        actions = [{"label": "Voltar", "url": reverse("nee:aluno_hub", args=[aluno.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
        if can(self.request.user, "nee.manage"):
            actions.append({"label": "Novo apoio", "url": reverse("nee:apoio_create", args=[aluno.pk]), "icon": "fa-solid fa-plus", "variant": "btn-primary"})
        actions.append({"label": "Exportar CSV", "url": f"{self.request.path}?q={escape(q)}&export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"})
        actions.append({"label": "Exportar PDF", "url": f"{self.request.path}?q={escape(q)}&export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"})
        return actions

    def get_headers(self, *args, **kwargs):
        return [
            {"label": "Turma"},
            {"label": "Tipo", "width": "220px"},
            {"label": "Ativo", "width": "120px"},
        ]

    def get_rows(self, request, page_obj):
        rows=[]
        for a in page_obj.object_list:
            turma = getattr(a.matricula, "turma", None)
            turma_txt = f"{turma.nome} — {getattr(turma,'ano_letivo','')}".strip() if turma else str(a.matricula)
            rows.append({
                "cells": [
                    {"text": turma_txt, "url": reverse("nee:apoio_detail", args=[a.pk])},
                    {"text": a.get_tipo_display() if hasattr(a, "get_tipo_display") else a.tipo},
                    {"text": "Sim" if a.ativo else "Não"},
                ],
                "can_edit": can(request.user, "nee.manage"),
                "edit_url": reverse("nee:apoio_update", args=[a.pk]),
            })
        return rows

    def get(self, request, *args, **kwargs):
        q = (request.GET.get(self.search_param) or "").strip()
        if request.GET.get("export") in ("csv","pdf"):
            qs = self.get_queryset(request)
            if q:
                qs = self.apply_search(qs, q)
            headers = ["Turma", "Tipo", "Ativo", "Descrição/Obs"]
            rows=[]
            for a in qs:
                turma = getattr(a.matricula, "turma", None)
                turma_txt = f"{turma.nome} — {getattr(turma,'ano_letivo','')}".strip() if turma else str(a.matricula)
                rows.append([turma_txt, (a.get_tipo_display() if hasattr(a, "get_tipo_display") else a.tipo), "Sim" if a.ativo else "Não", a.observacao or a.descricao or ""])
            if request.GET.get("export") == "csv":
                return export_csv("nee_apoios.csv", headers, rows)
            aluno = getattr(self, "_aluno", None)
            return export_pdf_table(request, filename="nee_apoios.pdf", title=f"NEE — Apoios ({aluno.nome})", headers=headers, rows=rows, subtitle="Apoios por matrícula", filtros=(f"Busca: {q}" if q else ""))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, request, **kwargs):
        ctx = super().get_context_data(request, **kwargs)
        ctx["aluno"] = getattr(self, "_aluno", None)
        return ctx


class ApoioCreateView(BaseCreateViewGepub):
    template_name = "nee/apoio_form.html"
    form_class = ApoioMatriculaForm
    title = "Novo apoio"
    subtitle = "Registrar apoio / acompanhamento"
    manage_perm = "nee.manage"
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["aluno"] = self.kwargs.get("aluno_id")
        return kwargs

    def get_actions(self, q: str = "", **kwargs):
        aluno_id = int(self.kwargs["aluno_id"])
        return [{"label": "Voltar", "url": reverse("nee:aluno_apoios", args=[aluno_id]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]

    def get_form(self, request, *args, **kwargs):
        aluno = get_scoped_aluno(request.user, int(self.kwargs["aluno_id"]))
        form = super().get_form(request, *args, **kwargs)
        matriculas = scope_filter_matriculas(request.user, Matricula.objects.filter(aluno=aluno)).order_by("-id")
        form.fields["matricula"].queryset = matriculas
        return form

    def get_success_url(self, request, obj=None) -> str:
        aluno_id = obj.matricula.aluno_id if obj and obj.matricula_id else int(self.kwargs["aluno_id"])
        return reverse("nee:aluno_apoios", args=[aluno_id])


class ApoioUpdateView(BaseUpdateViewGepub):
    template_name = "nee/apoio_form.html"
    form_class = ApoioMatriculaForm
    model = ApoioMatricula
    title = "Editar apoio"
    subtitle = "Atualizar apoio"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        return [{"label": "Voltar", "url": reverse("nee:apoio_detail", args=[obj.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]

    def get_form(self, request, *args, **kwargs):
        form = super().get_form(request, *args, **kwargs)
        # limita matriculas ao escopo do usuário
        matriculas = scope_filter_matriculas(request.user, Matricula.objects.all())
        form.fields["matricula"].queryset = matriculas
        return form

    def get_success_url(self, request, obj=None) -> str:
        return reverse("nee:aluno_apoios", args=[obj.matricula.aluno_id])


class ApoioDetailView(BaseDetailViewGepub):
    template_name = "nee/apoio_detail.html"
    model = ApoioMatricula
    title = "Apoio"
    subtitle = "Detalhes do apoio"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        aluno_id = obj.matricula.aluno_id
        actions = [
            {"label": "Voltar", "url": reverse("nee:aluno_apoios", args=[aluno_id]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Abrir aluno", "url": reverse("educacao:aluno_detail", args=[aluno_id]), "icon": "fa-solid fa-user", "variant": "btn--ghost"},
        ]
        if can(self.request.user, "nee.manage"):
            actions.append({"label": "Editar", "url": reverse("nee:apoio_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})
        return actions

    def get_fields(self, request, obj):
        turma = getattr(obj.matricula, "turma", None)
        turma_txt = f"{turma.nome} — {getattr(turma,'ano_letivo','')}".strip() if turma else str(obj.matricula)
        return [
            ("Matrícula", turma_txt),
            ("Tipo", obj.get_tipo_display() if hasattr(obj, "get_tipo_display") else obj.tipo),
            ("Ativo", "Sim" if obj.ativo else "Não"),
            ("Descrição", obj.descricao or "—"),
            ("Observação", obj.observacao or "—"),
        ]
