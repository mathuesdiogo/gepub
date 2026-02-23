from __future__ import annotations

from datetime import timedelta
from typing import Dict, List, Tuple

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from apps.core.rbac import scope_filter_alunos
from apps.educacao.models import Aluno

from .models import AlunoNecessidade, AcompanhamentoNEE, LaudoNEE, RecursoNEE


ALERTA_KINDS = {
    "sem-laudo": {
        "title": "Sem laudo",
        "subtitle": "Alunos com necessidade ativa e sem nenhum laudo cadastrado.",
        "icon": "fa-solid fa-file-circle-xmark",
    },
    "laudo-incompleto": {
        "title": "Laudo incompleto",
        "subtitle": "Laudo cadastrado, mas sem documento e sem texto.",
        "icon": "fa-solid fa-file-circle-exclamation",
    },
    "laudo-vencido": {
        "title": "Laudo vencido",
        "subtitle": "Alunos com laudo vencido (validade menor que hoje).",
        "icon": "fa-solid fa-calendar-xmark",
    },
    "laudo-vencendo-7d": {
        "title": "Laudo vencendo (7 dias)",
        "subtitle": "Validade entre hoje e os próximos 7 dias.",
        "icon": "fa-solid fa-calendar-day",
    },
    "sem-acompanhamento-30d": {
        "title": "Sem acompanhamento (30d+)",
        "subtitle": "Alunos sem acompanhamento recente (últimos 30 dias).",
        "icon": "fa-solid fa-clock",
    },
    "sem-recurso": {
        "title": "Sem recurso",
        "subtitle": "Alunos com necessidade ativa e sem recurso registrado.",
        "icon": "fa-solid fa-hand-holding-medical",
    },
}


def _base_alunos_nee(user):
    """
    Base: apenas alunos dentro do escopo do usuário + com alguma necessidade ativa.
    """
    qs = scope_filter_alunos(user, Aluno.objects.all())
    return qs.filter(necessidades__ativo=True).distinct()


def _qs_alerta(user, kind: str):
    base = _base_alunos_nee(user)
    today = timezone.localdate()

    # -------------------------
    # SEM LAUDO (nenhum registro)
    # -------------------------
    if kind == "sem-laudo":
        return base.annotate(
            has_laudo=Exists(
                LaudoNEE.objects.filter(aluno_id=OuterRef("pk"))
            )
        ).filter(has_laudo=False)

    # -------------------------
    # LAUDO INCOMPLETO
    # tem laudo mas sem documento e sem texto
    # -------------------------
    if kind == "laudo-incompleto":
        return base.filter(
            laudos_nee__isnull=False
        ).filter(
            Q(laudos_nee__documento__isnull=True) | Q(laudos_nee__documento=""),
            Q(laudos_nee__texto__isnull=True) | Q(laudos_nee__texto="")
        ).distinct()

    # -------------------------
    # LAUDO VENCIDO
    # -------------------------
    if kind == "laudo-vencido":
        return base.filter(
            laudos_nee__validade__isnull=False,
            laudos_nee__validade__lt=today
        ).distinct()

    # -------------------------
    # LAUDO VENCENDO EM 7 DIAS
    # -------------------------
    if kind == "laudo-vencendo-7d":
        limite = today + timedelta(days=7)
        return base.filter(
            laudos_nee__validade__isnull=False,
            laudos_nee__validade__gte=today,
            laudos_nee__validade__lte=limite
        ).distinct()

    # -------------------------
    # SEM ACOMPANHAMENTO RECENTE
    # -------------------------
    if kind == "sem-acompanhamento-30d":
        cutoff = today - timedelta(days=30)
        return base.annotate(
            has_recent=Exists(
                AcompanhamentoNEE.objects.filter(
                    aluno_id=OuterRef("pk"),
                    data__gte=cutoff
                )
            )
        ).filter(has_recent=False)

    # -------------------------
    # SEM RECURSO
    # -------------------------
    if kind == "sem-recurso":
        return base.annotate(
            has_recurso=Exists(
                RecursoNEE.objects.filter(aluno_id=OuterRef("pk"))
            )
        ).filter(has_recurso=False)

    # fallback
    return base.none()


@login_required
def alertas_index(request):
    cards: List[Dict[str, str]] = []

    for kind, meta in ALERTA_KINDS.items():
        qs = _qs_alerta(request.user, kind)
        total = qs.count()
        cards.append(
            {
                "title": meta["title"],
                "subtitle": meta["subtitle"],
                "icon": meta["icon"],
                "total": str(total),
                "url": reverse("nee:alertas_lista", kwargs={"kind": kind}),
            }
        )

    actions = [
        {"label": "Voltar", "url": reverse("nee:index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
    ]

    return render(
        request,
        "nee/alertas/index.html",
        {
            "actions": actions,
            "cards": cards,
        },
    )


@login_required
def alertas_lista(request, kind: str):
    meta = ALERTA_KINDS.get(kind)
    if not meta:
        # simples: volta pro index
        return render(
            request,
            "nee/alertas/alunos_list.html",
            {
                "actions": [{"label": "Voltar", "url": reverse("nee:alertas_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}],
                "title": "Alerta",
                "subtitle": "Tipo de alerta inválido.",
                "headers": [{"label": "Aluno"}],
                "rows": [],
                "page_obj": None,
                "empty_title": "Nada a listar",
                "empty_text": "Este alerta não existe.",
            },
        )

    qs = _qs_alerta(request.user, kind).order_by("nome")

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    headers = [
        {"label": "Aluno"},
        {"label": "CPF", "width": "150px"},
        {"label": "NIS", "width": "150px"},
        {"label": "Ações", "width": "140px"},
    ]

    rows = []
    for a in page_obj.object_list:
        rows.append(
            {
                "cells": [
                    {"text": a.nome, "url": reverse("nee:aluno_hub", args=[a.pk])},
                    {"text": getattr(a, "cpf", None) or "—"},
                    {"text": getattr(a, "nis", None) or "—"},
                    {"text": "Abrir", "url": reverse("nee:aluno_hub", args=[a.pk])},
                ],
                "can_edit": False,
            }
        )

    actions = [
        {"label": "Voltar", "url": reverse("nee:alertas_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
    ]

    return render(
        request,
        "nee/alertas/alunos_list.html",
        {
            "actions": actions,
            "title": f"Alertas — {meta['title']}",
            "subtitle": meta["subtitle"],
            "headers": headers,
            "rows": rows,
            "page_obj": page_obj,
            "empty_title": "Sem ocorrências",
            "empty_text": "Nenhum aluno encontrado para este alerta.",
        },
    )