from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin

from apps.core.views_gepub import (
    BaseListViewGepub,
    BaseCreateViewGepub,
    BaseUpdateViewGepub,
    BaseDetailViewGepub,
)
from apps.educacao.models import Aluno

from .models import LaudoNEE
from .forms import LaudoNEEForm


class LaudoListView(LoginRequiredMixin, BaseListViewGepub):
    template_name = "nee/laudo_list.html"
    paginate_by = 20
    manage_perm = "nee.manage"

    # BaseListViewGepub chama get_queryset(request)
    def get_queryset(self, request, *args, **kwargs):
        aluno_id = int(self.kwargs["aluno_id"])
        self._aluno = get_object_or_404(Aluno, pk=aluno_id)
        return LaudoNEE.objects.filter(aluno_id=aluno_id).order_by("-data_emissao", "-id")

    def get_actions(self, q: str = "", **kwargs):
        aluno_id = int(self.kwargs["aluno_id"])
        aluno = getattr(self, "_aluno", None)
        actions = [
            {
                "label": "Voltar",
                "url": reverse("nee:aluno_hub", args=[aluno_id]),
                "icon": "fa-solid fa-arrow-left",
                "variant": "btn--ghost",
            },
        ]
        if aluno:
            actions.append(
                {
                    "label": "Abrir aluno",
                    "url": reverse("educacao:aluno_detail", args=[aluno.pk]),
                    "icon": "fa-solid fa-user",
                    "variant": "btn--ghost",
                }
            )
        actions.append(
            {
                "label": "Novo laudo",
                "url": reverse("nee:laudo_create", args=[aluno_id]),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            }
        )
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
            rows.append(
                {
                    "cells": [
                        {"text": l.numero or "—", "url": reverse("nee:laudo_detail", args=[l.pk])},
                        {"text": l.data_emissao.strftime("%d/%m/%Y") if l.data_emissao else "—"},
                        {"text": l.validade.strftime("%d/%m/%Y") if l.validade else "—"},
                        {"text": l.profissional or "—"},
                    ],
                    "can_edit": True,
                    "edit_url": reverse("nee:laudo_update", args=[l.pk]),
                }
            )
        return rows

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if getattr(self, "_aluno", None):
            ctx["aluno"] = self._aluno
        return ctx


class LaudoCreateView(LoginRequiredMixin, BaseCreateViewGepub):
    template_name = "nee/laudo_form.html"
    form_class = LaudoNEEForm
    title = "Novo laudo"
    subtitle = "Cadastrar laudo para o aluno"
    manage_perm = "nee.manage"

    def form_valid(self, *args, **kwargs):
        # Compat: BaseCreateViewGepub pode chamar form_valid(request, form)
        # ou o padrão Django form_valid(form).
        if len(args) >= 2 and hasattr(args[0], "method") and hasattr(args[1], "is_valid"):
            request, form = args[0], args[1]
        else:
            form = args[0]

        aluno_id = int(self.kwargs["aluno_id"])
        form.instance.aluno = get_object_or_404(Aluno, pk=aluno_id)

        # chama o BaseCreateViewGepub com a assinatura que ele espera
        return super().form_valid(request, form) if "request" in locals() else super().form_valid(request, form)

    def get_actions(self, q: str = "", **kwargs):
        aluno_id = int(self.kwargs["aluno_id"])
        return [
            {
                "label": "Voltar",
                "url": reverse("nee:aluno_laudos", args=[aluno_id]),
                "icon": "fa-solid fa-arrow-left",
                "variant": "btn--ghost",
            },
        ]

    # BaseCreateViewGepub chama get_success_url(request, obj)
    def get_success_url(self, request, obj=None):
        return reverse("nee:aluno_laudos", args=[obj.aluno_id])


class LaudoUpdateView(LoginRequiredMixin, BaseUpdateViewGepub):
    template_name = "nee/laudo_form.html"
    form_class = LaudoNEEForm
    model = LaudoNEE
    title = "Editar laudo"
    subtitle = "Atualizar laudo do aluno"
    manage_perm = "nee.manage"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = getattr(self, "object", None)
        if obj is None and "object" in ctx:
            obj = ctx["object"]
        if obj is not None:
            ctx["aluno"] = obj.aluno
        return ctx


    def get_actions(self, q: str = "", obj=None, **kwargs):
        return [
            {
                "label": "Voltar",
                "url": reverse("nee:laudo_detail", args=[obj.pk]),
                "icon": "fa-solid fa-arrow-left",
                "variant": "btn--ghost",
            },
        ]

    def get_success_url(self, request, obj=None):
        return reverse("nee:aluno_laudos", args=[obj.aluno_id])


class LaudoDetailView(LoginRequiredMixin, BaseDetailViewGepub):
    template_name = "nee/laudo_detail.html"
    model = LaudoNEE
    title = "Laudo"
    subtitle = "Detalhes do laudo"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        return [
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
            {
                "label": "Editar",
                "url": reverse("nee:laudo_update", args=[obj.pk]),
                "icon": "fa-solid fa-pen",
                "variant": "btn-primary",
            },
        ]