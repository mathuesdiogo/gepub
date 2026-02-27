from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import scope_filter_alunos, scope_filter_matriculas, scope_filter_turmas

from .models import Aluno, Matricula, Turma
from .models_diario import Avaliacao, DiarioTurma, Nota
from .models_periodos import PeriodoLetivo
from .services_academico import calc_historico_resumo


@login_required
@require_perm("educacao.view")
def portal_professor(request):
    user = request.user
    role = getattr(getattr(user, "profile", None), "role", "")

    diarios_qs = DiarioTurma.objects.select_related("turma", "turma__unidade", "professor").order_by("-ano_letivo", "turma__nome")
    if role == "PROFESSOR":
        diarios_qs = diarios_qs.filter(professor=user)
    else:
        turmas_qs = scope_filter_turmas(user, Turma.objects.all())
        diarios_qs = diarios_qs.filter(turma__in=turmas_qs)

    diarios = list(diarios_qs[:40])
    rows = []
    total_aulas = 0
    total_avaliacoes = 0
    total_pendencias = 0

    for d in diarios:
        aulas_count = d.aulas.count()
        avaliacoes_count = d.avaliacoes.count()
        total_aulas += aulas_count
        total_avaliacoes += avaliacoes_count

        pendencias = 0
        ultima_avaliacao = Avaliacao.objects.filter(diario=d).order_by("-data", "-id").first()
        if ultima_avaliacao:
            ativos = Matricula.objects.filter(turma=d.turma, situacao=Matricula.Situacao.ATIVA).count()
            lancadas = Nota.objects.filter(avaliacao=ultima_avaliacao).count()
            pendencias = max(ativos - lancadas, 0)
            total_pendencias += pendencias

        rows.append(
            {
                "cells": [
                    {"text": d.turma.nome, "url": reverse("educacao:diario_detail", args=[d.pk])},
                    {"text": getattr(getattr(d, "professor", None), "username", "—")},
                    {"text": str(d.ano_letivo)},
                    {"text": str(aulas_count)},
                    {"text": str(avaliacoes_count)},
                    {"text": str(pendencias)},
                    {"text": "Abrir avaliações", "url": reverse("educacao:avaliacao_list", args=[d.pk])},
                ]
            }
        )

    actions = [
        {"label": "Diário de Classe", "url": reverse("educacao:meus_diarios"), "icon": "fa-solid fa-book", "variant": "btn--ghost"},
    ]

    return render(
        request,
        "educacao/portal_professor.html",
        {
            "actions": actions,
            "total_diarios": len(diarios),
            "total_aulas": total_aulas,
            "total_avaliacoes": total_avaliacoes,
            "total_pendencias": total_pendencias,
            "headers": [
                {"label": "Turma"},
                {"label": "Professor", "width": "180px"},
                {"label": "Ano", "width": "90px"},
                {"label": "Aulas", "width": "90px"},
                {"label": "Avaliações", "width": "110px"},
                {"label": "Pendências", "width": "110px"},
                {"label": "Ação", "width": "140px"},
            ],
            "rows": rows,
        },
    )


@login_required
@require_perm("educacao.view")
def portal_aluno(request, pk: int):
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

    rows = []
    for m in matriculas:
        periodos = PeriodoLetivo.objects.filter(ano_letivo=m.turma.ano_letivo, ativo=True).order_by("numero")
        media_final, freq_final, resultado = calc_historico_resumo(turma=m.turma, periodos=periodos, aluno_id=aluno.id)
        rows.append(
            {
                "cells": [
                    {"text": str(m.turma.ano_letivo)},
                    {"text": m.turma.nome, "url": reverse("educacao:turma_detail", args=[m.turma.pk])},
                    {"text": m.turma.unidade.nome},
                    {"text": m.get_situacao_display()},
                    {"text": str(media_final) if media_final is not None else "—"},
                    {"text": str(freq_final) if freq_final is not None else "—"},
                    {"text": resultado},
                ]
            }
        )

    actions = [
        {"label": "Voltar", "url": reverse("educacao:aluno_detail", args=[aluno.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Histórico Completo", "url": reverse("educacao:historico_aluno", args=[aluno.pk]), "icon": "fa-solid fa-scroll", "variant": "btn--ghost"},
    ]

    return render(
        request,
        "educacao/portal_aluno.html",
        {
            "aluno": aluno,
            "actions": actions,
            "headers": [
                {"label": "Ano", "width": "90px"},
                {"label": "Turma"},
                {"label": "Unidade"},
                {"label": "Situação", "width": "130px"},
                {"label": "Média", "width": "110px"},
                {"label": "Frequência (%)", "width": "130px"},
                {"label": "Resultado", "width": "130px"},
            ],
            "rows": rows,
        },
    )
