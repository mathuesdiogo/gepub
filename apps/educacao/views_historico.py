from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.exports import export_csv, export_pdf_table
from apps.core.rbac import scope_filter_alunos, scope_filter_matriculas

from .models import Aluno, AlunoCertificado, Matricula
from .models_periodos import PeriodoLetivo
from .services_academico import calc_historico_resumo


@login_required
@require_perm("educacao.view")
def historico_aluno(request, pk: int):
    aluno_qs = scope_filter_alunos(request.user, Aluno.objects.all())
    aluno = get_object_or_404(aluno_qs, pk=pk)

    matriculas = scope_filter_matriculas(
        request.user,
        Matricula.objects.select_related(
            "turma",
            "turma__unidade",
            "turma__unidade__secretaria",
            "turma__unidade__secretaria__municipio",
        )
        .filter(aluno=aluno)
        .order_by("-turma__ano_letivo", "turma__nome"),
    )

    rows_calc = []
    for m in matriculas:
        periodos = PeriodoLetivo.objects.filter(ano_letivo=m.turma.ano_letivo, ativo=True).order_by("numero")
        media_final, freq_final, resultado = calc_historico_resumo(
            turma=m.turma,
            periodos=periodos,
            aluno_id=aluno.id,
            media_corte=Decimal("6.00"),
            frequencia_corte=Decimal("75.00"),
        )
        rows_calc.append(
            {
                "turma": m.turma.nome,
                "ano": m.turma.ano_letivo,
                "unidade": getattr(getattr(m, "turma", None), "unidade", None),
                "modalidade": m.turma.get_modalidade_display() if hasattr(m.turma, "get_modalidade_display") else m.turma.modalidade,
                "etapa": m.turma.get_etapa_display() if hasattr(m.turma, "get_etapa_display") else m.turma.etapa,
                "curso": getattr(getattr(m.turma, "curso", None), "nome", "—"),
                "situacao": m.get_situacao_display(),
                "media": media_final,
                "frequencia": freq_final,
                "resultado": resultado,
            }
        )

    certificados = AlunoCertificado.objects.filter(aluno=aluno, ativo=True).order_by("-data_emissao", "-id")

    export = (request.GET.get("export") or "").strip().lower()
    if export in {"csv", "pdf"}:
        headers = [
            "Ano",
            "Turma",
            "Unidade",
            "Modalidade",
            "Etapa",
            "Curso",
            "Situação",
            "Média Final",
            "Frequência (%)",
            "Resultado",
        ]
        rows = []
        for r in rows_calc:
            rows.append(
                [
                    str(r["ano"]),
                    r["turma"],
                    getattr(r["unidade"], "nome", "—"),
                    r["modalidade"],
                    r["etapa"],
                    r["curso"],
                    r["situacao"],
                    str(r["media"]) if r["media"] is not None else "—",
                    str(r["frequencia"]) if r["frequencia"] is not None else "—",
                    r["resultado"],
                ]
            )

        if export == "csv":
            return export_csv(f"historico_aluno_{aluno.pk}.csv", headers, rows)

        filtros = f"Aluno={aluno.nome}"
        return export_pdf_table(
            request,
            filename=f"historico_aluno_{aluno.pk}.pdf",
            title="Histórico Escolar do Aluno",
            headers=headers,
            rows=rows,
            filtros=filtros,
        )

    actions = [
        {"label": "Voltar", "url": reverse("educacao:aluno_detail", args=[aluno.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Exportar CSV", "url": reverse("educacao:historico_aluno", args=[aluno.pk]) + "?export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "Exportar PDF", "url": reverse("educacao:historico_aluno", args=[aluno.pk]) + "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]

    headers = [
        {"label": "Ano", "width": "110px"},
        {"label": "Turma"},
        {"label": "Unidade"},
        {"label": "Modalidade"},
        {"label": "Etapa"},
        {"label": "Curso"},
        {"label": "Situação", "width": "130px"},
        {"label": "Média Final", "width": "130px"},
        {"label": "Frequência (%)", "width": "140px"},
        {"label": "Resultado", "width": "130px"},
    ]
    rows = []
    for r in rows_calc:
        rows.append(
            {
                "cells": [
                    {"text": str(r["ano"])},
                    {"text": r["turma"]},
                    {"text": getattr(r["unidade"], "nome", "—")},
                    {"text": r["modalidade"]},
                    {"text": r["etapa"]},
                    {"text": r["curso"]},
                    {"text": r["situacao"]},
                    {"text": str(r["media"]) if r["media"] is not None else "—"},
                    {"text": str(r["frequencia"]) if r["frequencia"] is not None else "—"},
                    {"text": r["resultado"]},
                ]
            }
        )

    return render(
        request,
        "educacao/historico_aluno.html",
        {
            "aluno": aluno,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "certificados": certificados,
        },
    )
