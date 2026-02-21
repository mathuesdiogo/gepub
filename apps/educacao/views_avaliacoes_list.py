from __future__ import annotations

from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.urls import reverse

from apps.core.exports import export_pdf_table
from apps.core.rbac import can, scope_filter_turmas
from apps.core.views_gepub import BaseListViewGepub

from .models import Turma
from .models_diario import DiarioTurma, Avaliacao


def _is_professor(user) -> bool:
    return getattr(getattr(user, "profile", None), "role", "") == "PROFESSOR"


def _can_edit_diario(user, diario: DiarioTurma) -> bool:
    if can(user, "educacao.manage"):
        return True
    if not _is_professor(user):
        return False
    return getattr(diario, "professor_id", None) == getattr(user, "id", None)


def _can_view_diario(user, diario: DiarioTurma) -> bool:
    if not can(user, "educacao.view"):
        return False
    return scope_filter_turmas(user, Turma.objects.filter(pk=diario.turma_id)).exists()


class AvaliacaoListView(BaseListViewGepub):
    template_name = "educacao/avaliacao_list.html"
    url_name = "educacao:avaliacao_list"
    perm_required = "educacao.view"

    page_title = "Avaliações"
    page_subtitle = "Crie e lance notas por período"

    paginate_by = 20
    ordering = "-data"

    search_fields = ["titulo"]

    def get_url_args(self, **kwargs):
        return [kwargs.get("pk")]

    def get_base_queryset(self):
        # queryset real é por diário; retornamos vazio aqui e montamos no apply_filters
        return Avaliacao.objects.none()

    def apply_filters(self, qs, *, q: str, ano: int | None, **kwargs):
        pk = kwargs.get("pk")
        diario = get_object_or_404(
            DiarioTurma.objects.select_related("turma", "turma__unidade", "professor"),
            pk=pk,
        )
        self.diario = diario  # para contexto extra

        if not _can_view_diario(self.request.user, diario):
            # BaseList não sabe lidar com perm contextual, então fazemos aqui
            raise PermissionError

        return Avaliacao.objects.filter(diario=diario).order_by("-data", "-id")

    def maybe_export(self, *, qs, q: str, ano: int | None, **kwargs):
        export = (self.request.GET.get("export") or "").strip().lower()
        if export != "pdf":
            return None

        diario = getattr(self, "diario", None)
        headers = ["Título", "Data", "Peso"]
        rows = []
        for a in qs:
            rows.append([
                a.titulo or "—",
                a.data.strftime("%d/%m/%Y") if a.data else "—",
                str(a.peso) if a.peso is not None else "—",
            ])
        filtros = ""
        if diario:
            filtros = f"Turma={diario.turma.nome} | Ano={diario.ano_letivo} | Professor={getattr(diario.professor, 'username', '-')}"
        return export_pdf_table(
            self.request,
            filename="avaliacoes.pdf",
            title="Avaliações — Diário de Classe",
            headers=headers,
            rows=rows,
            filtros=filtros,
        )

    def get_actions(self, *, q: str, ano: int | None, **kwargs):
        diario = getattr(self, "diario", None)
        actions = []
        if diario:
            actions.append({
                "label": "Voltar",
                "url": reverse("educacao:diario_detail", args=[diario.pk]),
                "icon": "fa-solid fa-arrow-left",
                "variant": "btn--ghost",
            })
            actions.append({
                "label": "Imprimir PDF",
                "url": reverse("educacao:avaliacao_list", args=[diario.pk]) + "?export=pdf",
                "icon": "fa-solid fa-file-pdf",
                "variant": "btn--ghost",
            })
            if _can_edit_diario(self.request.user, diario):
                actions.append({
                    "label": "Nova Avaliação",
                    "url": reverse("educacao:avaliacao_create", args=[diario.pk]),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                })
        return actions

    def get_headers(self, **kwargs):
        return [
            {"label": "Título"},
            {"label": "Data", "width": "140px"},
            {"label": "Peso", "width": "110px"},
            {"label": "Ações", "width": "180px"},
        ]


    def get_extra_context(self, **kwargs):
        return {
            "diario": getattr(self, "diario", None),
            "can_edit": _can_edit_diario(self.request.user, getattr(self, "diario", None)),
        }

    def get_rows(self, objs, **kwargs):
        rows = []
        for a in objs:
            rows.append({
                "cells": [
                    {"text": a.titulo or "—"},
                    {"text": a.data.strftime("%d/%m/%Y") if a.data else "—"},
                    {"text": str(a.peso) if a.peso is not None else "—"},
                    {"text": "Lançar notas", "url": reverse("educacao:notas_lancar", args=[a.pk])},
                ],
                "can_edit": False,
                "edit_url": "",
            })
        return rows

