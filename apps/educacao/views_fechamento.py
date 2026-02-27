from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import scope_filter_turmas

from .forms_fechamento import FechamentoPeriodoTurmaForm
from .models import Matricula, Turma
from .models_periodos import FechamentoPeriodoTurma, PeriodoLetivo
from .services_academico import calc_periodo_metrics_by_aluno, classify_resultado


@login_required
@require_perm("educacao.manage")
def fechamento_turma_periodo(request, pk: int):
    turma_qs = scope_filter_turmas(
        request.user,
        Turma.objects.select_related("unidade", "unidade__secretaria", "unidade__secretaria__municipio"),
    )
    turma = get_object_or_404(turma_qs, pk=pk)

    periodos = PeriodoLetivo.objects.filter(ano_letivo=turma.ano_letivo, ativo=True).order_by("numero")
    if not periodos.exists():
        messages.warning(request, "Cadastre períodos letivos para realizar o fechamento.")
        return redirect("educacao:periodo_list")

    periodo_id = (request.GET.get("periodo") or request.POST.get("periodo") or "").strip()
    if periodo_id.isdigit():
        periodo = get_object_or_404(periodos, pk=int(periodo_id))
    else:
        periodo = periodos.first()

    fechamento = FechamentoPeriodoTurma.objects.filter(turma=turma, periodo=periodo).first()
    if request.method == "POST":
        form = FechamentoPeriodoTurmaForm(request.POST, instance=fechamento)
    else:
        form = FechamentoPeriodoTurmaForm(instance=fechamento)

    matriculas = (
        Matricula.objects.filter(turma=turma, situacao=Matricula.Situacao.ATIVA)
        .select_related("aluno")
        .order_by("aluno__nome")
    )
    aluno_ids = list(matriculas.values_list("aluno_id", flat=True))
    media_map, freq_map, total_aulas = calc_periodo_metrics_by_aluno(turma=turma, periodo=periodo, aluno_ids=aluno_ids)

    media_corte = form.initial.get("media_corte") if form.initial else Decimal("6.00")
    freq_corte = form.initial.get("frequencia_corte") if form.initial else Decimal("75.00")
    if form.is_bound and form.is_valid():
        media_corte = form.cleaned_data["media_corte"]
        freq_corte = form.cleaned_data["frequencia_corte"]

    rows_preview = []
    aprovados = 0
    recuperacao = 0
    reprovados = 0
    for m in matriculas:
        media = media_map.get(m.aluno_id)
        freq = freq_map.get(m.aluno_id)
        resultado = classify_resultado(
            media=media,
            frequencia=freq,
            media_corte=Decimal(str(media_corte)),
            frequencia_corte=Decimal(str(freq_corte)),
        )
        if resultado == "Aprovado":
            aprovados += 1
        elif resultado == "Recuperação":
            recuperacao += 1
        elif resultado == "Reprovado":
            reprovados += 1
        rows_preview.append(
            {
                "cells": [
                    {"text": m.aluno.nome},
                    {"text": str(media) if media is not None else "—"},
                    {"text": str(freq) if freq is not None else "—"},
                    {"text": resultado},
                ]
            }
        )

    if request.method == "POST":
        if form.is_valid():
            fechamento = form.save(commit=False)
            fechamento.turma = turma
            fechamento.periodo = periodo
            fechamento.total_alunos = len(aluno_ids)
            fechamento.aprovados = aprovados
            fechamento.recuperacao = recuperacao
            fechamento.reprovados = reprovados
            fechamento.fechado_por = request.user
            fechamento.save()
            messages.success(request, "Fechamento do período salvo com sucesso.")
            return redirect(reverse("educacao:fechamento_turma_periodo", args=[turma.pk]) + f"?periodo={periodo.pk}")
        messages.error(request, "Corrija os erros do fechamento.")

    actions = [
        {"label": "Voltar", "url": reverse("educacao:turma_detail", args=[turma.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Boletim do Período", "url": reverse("educacao:boletim_turma_periodo", args=[turma.pk]) + f"?periodo={periodo.pk}", "icon": "fa-solid fa-clipboard-list", "variant": "btn--ghost"},
    ]

    periodo_options = "".join(
        [
            f'<option value="{p.pk}" {"selected" if p.pk == periodo.pk else ""}>{p}</option>'
            for p in periodos
        ]
    )
    extra_filters = f"""
    <div class="filter-bar__field">
      <label>Período</label>
      <select name="periodo">{periodo_options}</select>
    </div>
    """
    top_extra = f'<input type="hidden" name="periodo" value="{periodo.pk}" />'

    return render(
        request,
        "educacao/fechamento_turma_periodo.html",
        {
            "turma": turma,
            "periodo": periodo,
            "actions": actions,
            "action_url": reverse("educacao:fechamento_turma_periodo", args=[turma.pk]),
            "clear_url": reverse("educacao:fechamento_turma_periodo", args=[turma.pk]),
            "has_filters": bool(periodo_id),
            "extra_filters": extra_filters,
            "top_extra": top_extra,
            "form": form,
            "total_aulas": total_aulas,
            "total_alunos": len(aluno_ids),
            "aprovados": aprovados,
            "recuperacao": recuperacao,
            "reprovados": reprovados,
            "headers_preview": [
                {"label": "Aluno"},
                {"label": "Média", "width": "120px"},
                {"label": "Frequência (%)", "width": "140px"},
                {"label": "Resultado", "width": "140px"},
            ],
            "rows_preview": rows_preview,
        },
    )
