from __future__ import annotations
from django.shortcuts import get_object_or_404
from apps.educacao.models import Aluno

from django.db.models import Q
from django.urls import reverse
from django.utils.html import escape

from apps.core.rbac import can
from apps.core.views_gepub import BaseCreateViewGepub, BaseDetailViewGepub, BaseListViewGepub, BaseUpdateViewGepub
from apps.core.exports import export_csv, export_pdf_table

from .forms import AcompanhamentoNEEForm
from .models import AcompanhamentoNEE
from .utils import get_scoped_aluno


class AcompanhamentoListView(BaseListViewGepub):
    template_name = "nee/acompanhamento_list.html"
    paginate_by = 20
    manage_perm = "nee.manage"

    def get_base_queryset(self):
        aluno = get_scoped_aluno(self.request.user, int(self.kwargs["aluno_id"]))
        self._aluno = aluno
        return AcompanhamentoNEE.objects.select_related("autor").filter(aluno=aluno).order_by("-data", "-id")

    def apply_search(self, qs, q: str, **kwargs):
        if q:
            qs = qs.filter(Q(descricao__icontains=q) | Q(tipo_evento__icontains=q) | Q(autor__username__icontains=q))
        return qs

    def get_actions(self, q: str = "", **kwargs):
        aluno = getattr(self, "_aluno", None)
        actions = [{"label": "Voltar", "url": reverse("nee:aluno_hub", args=[aluno.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
        if can(self.request.user, "nee.manage"):
            actions.append({"label": "Novo evento", "url": reverse("nee:acompanhamento_create", args=[aluno.pk]), "icon": "fa-solid fa-plus", "variant": "btn-primary"})
        actions.append({"label": "Exportar CSV", "url": f"{self.request.path}?q={escape(q)}&export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"})
        actions.append({"label": "Exportar PDF", "url": f"{self.request.path}?q={escape(q)}&export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"})
        return actions

    def get_headers(self, *args, **kwargs):
        return [
            {"label": "Data", "width": "140px"},
            {"label": "Tipo", "width": "180px"},
            {"label": "Visibilidade", "width": "180px"},
            {"label": "Descrição"},
        ]

    def get_rows(self, request, page_obj):
        rows=[]
        for e in page_obj.object_list:
            rows.append({
                "cells": [
                    {"text": e.data.strftime("%d/%m/%Y"), "url": reverse("nee:acompanhamento_detail", args=[e.pk])},
                    {"text": e.get_tipo_evento_display()},
                    {"text": e.get_visibilidade_display()},
                    {"text": (e.descricao[:120] + "…") if len(e.descricao) > 120 else e.descricao},
                ],
                "can_edit": can(request.user, "nee.manage"),
                "edit_url": reverse("nee:acompanhamento_update", args=[e.pk]),
            })
        return rows

    def get(self, request, *args, **kwargs):
        q = (request.GET.get(self.search_param) or "").strip()
        if request.GET.get("export") in ("csv","pdf"):
            qs = self.get_queryset(request)
            if q:
                qs = self.apply_search(qs, q)
            headers = ["Data", "Tipo", "Visibilidade", "Descrição"]
            rows = [[e.data.strftime("%d/%m/%Y"), e.get_tipo_evento_display(), e.get_visibilidade_display(), e.descricao] for e in qs]
            if request.GET.get("export") == "csv":
                return export_csv("nee_timeline.csv", headers, rows)
            aluno = getattr(self, "_aluno", None)
            return export_pdf_table(request, filename="nee_timeline.pdf", title=f"NEE — Timeline ({aluno.nome})", headers=headers, rows=rows, subtitle="Acompanhamentos", filtros=(f"Busca: {q}" if q else ""))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, request, **kwargs):
        ctx = super().get_context_data(request, **kwargs)
        ctx["aluno"] = getattr(self, "_aluno", None)
        return ctx


class AcompanhamentoCreateView(BaseCreateViewGepub):
    template_name = "nee/acompanhamento_form.html"
    form_class = AcompanhamentoNEEForm
    title = "Novo evento"
    subtitle = "Registrar acompanhamento"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", **kwargs):
        aluno_id = int(self.kwargs["aluno_id"])
        return [{
            "label": "Voltar",
            "url": reverse("nee:aluno_acompanhamentos", args=[aluno_id]),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }]

    def form_valid(self, request, form):
        aluno_id = int(self.kwargs["aluno_id"])
        form.instance.aluno = get_object_or_404(Aluno, pk=aluno_id)

        # seta autor automaticamente
        if hasattr(form.instance, "autor_id") and not form.instance.autor_id:
            form.instance.autor = request.user

        return super().form_valid(request, form)

    def get_success_url(self, request, obj=None):
        return reverse("nee:aluno_acompanhamentos", args=[obj.aluno_id])


class AcompanhamentoUpdateView(BaseUpdateViewGepub):
    template_name = "nee/acompanhamento_form.html"
    form_class = AcompanhamentoNEEForm
    model = AcompanhamentoNEE
    title = "Editar evento"
    subtitle = "Atualizar acompanhamento"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        return [{"label": "Voltar", "url": reverse("nee:acompanhamento_detail", args=[obj.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]

    def post(self, request, pk: int, *args, **kwargs):
        # autor não é editável no form — mantém
        return super().post(request, pk, *args, **kwargs)

    def get_success_url(self, request, obj=None) -> str:
        return reverse("nee:aluno_acompanhamentos", args=[obj.aluno_id])


class AcompanhamentoDetailView(BaseDetailViewGepub):
    template_name = "nee/acompanhamento_detail.html"
    model = AcompanhamentoNEE
    title = "Evento"
    subtitle = "Detalhes do acompanhamento"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        actions = [
            {"label": "Voltar", "url": reverse("nee:aluno_acompanhamentos", args=[obj.aluno_id]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Abrir aluno", "url": reverse("nee:aluno_hub", args=[obj.aluno_id]), "icon": "fa-solid fa-user", "variant": "btn--ghost"},
        ]
        if can(self.request.user, "nee.manage"):
            actions.append({"label": "Editar", "url": reverse("nee:acompanhamento_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})
        return actions

    def get_fields(self, request, obj):
        return [
            ("Aluno", str(obj.aluno)),
            ("Data", obj.data.strftime("%d/%m/%Y")),
            ("Tipo", obj.get_tipo_evento_display()),
            ("Visibilidade", obj.get_visibilidade_display()),
            ("Autor", getattr(obj.autor, "username", "—")),
            ("Descrição", obj.descricao),
        ]
