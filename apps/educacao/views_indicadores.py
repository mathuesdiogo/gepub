from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.shortcuts import render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import scope_filter_matriculas, scope_filter_turmas, scope_filter_unidades
from apps.org.models import Unidade

from .models import Matricula, Turma
from .models_diario import Frequencia, Nota


@login_required
@require_perm("educacao.view")
def indicadores_gerenciais(request):
    unidades_qs = scope_filter_unidades(
        request.user,
        Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO).order_by("nome"),
    )
    turmas_qs = scope_filter_turmas(
        request.user,
        Turma.objects.select_related("unidade"),
    )
    matriculas_qs = scope_filter_matriculas(
        request.user,
        Matricula.objects.select_related("turma", "turma__unidade", "aluno"),
    )

    total_unidades = unidades_qs.count()
    total_turmas = turmas_qs.count()
    total_matriculas = matriculas_qs.count()
    total_alunos_unicos = matriculas_qs.values("aluno_id").distinct().count()
    evasao = matriculas_qs.filter(situacao=Matricula.Situacao.EVADIDO).count()
    canceladas = matriculas_qs.filter(situacao=Matricula.Situacao.CANCELADO).count()
    transferidas = matriculas_qs.filter(situacao=Matricula.Situacao.TRANSFERIDO).count()

    status_rows = list(
        matriculas_qs.values("situacao")
        .annotate(total=Count("id"))
        .order_by("situacao")
    )
    status_labels = [r["situacao"] for r in status_rows]
    status_values = [r["total"] for r in status_rows]

    freq_qs = Frequencia.objects.filter(
        aula__diario__turma__in=turmas_qs,
        aluno_id__in=matriculas_qs.values_list("aluno_id", flat=True),
    )
    freq_total = freq_qs.count()
    freq_presentes = freq_qs.filter(status=Frequencia.Status.PRESENTE).count()
    frequencia_pct = round((freq_presentes / freq_total) * 100, 1) if freq_total else 0.0

    nota_media = Nota.objects.filter(
        avaliacao__diario__turma__in=turmas_qs,
        aluno_id__in=matriculas_qs.values_list("aluno_id", flat=True),
    ).aggregate(media=Avg("valor"))["media"]
    nota_media = Decimal(str(nota_media or 0)).quantize(Decimal("0.01"))

    producao_unidade = (
        matriculas_qs.values("turma__unidade__nome")
        .annotate(total=Count("id"))
        .order_by("-total", "turma__unidade__nome")
    )

    headers = [
        {"label": "Unidade"},
        {"label": "Matrículas", "width": "120px"},
    ]
    rows = []
    for r in producao_unidade:
        rows.append(
            {
                "cells": [
                    {"text": r["turma__unidade__nome"] or "—"},
                    {"text": str(r["total"])},
                ]
            }
        )

    actions = [
        {"label": "Relatório Mensal", "url": reverse("educacao:relatorio_mensal"), "icon": "fa-solid fa-chart-column", "variant": "btn--ghost"},
        {"label": "Censo Escolar", "url": reverse("educacao:censo_escolar"), "icon": "fa-solid fa-database", "variant": "btn--ghost"},
    ]

    return render(
        request,
        "educacao/indicadores_gerenciais.html",
        {
            "actions": actions,
            "total_unidades": total_unidades,
            "total_turmas": total_turmas,
            "total_matriculas": total_matriculas,
            "total_alunos_unicos": total_alunos_unicos,
            "evasao": evasao,
            "canceladas": canceladas,
            "transferidas": transferidas,
            "frequencia_pct": frequencia_pct,
            "nota_media": nota_media,
            "status_labels": status_labels,
            "status_values": status_values,
            "headers": headers,
            "rows": rows,
        },
    )
