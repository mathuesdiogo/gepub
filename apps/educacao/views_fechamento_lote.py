from __future__ import annotations

from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.decorators import require_perm
from apps.core.rbac import scope_filter_turmas, scope_filter_unidades
from apps.org.models import Secretaria, Unidade

from .models import Matricula, Turma
from .models_periodos import FechamentoPeriodoTurma, PeriodoLetivo
from .services_academico import calc_periodo_metrics_by_aluno, classify_resultado


def _unidades_educacao_scope(user):
    return scope_filter_unidades(
        user,
        Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO).select_related("secretaria", "secretaria__municipio"),
    )


def _secretarias_from_unidades(unidades_qs):
    return (
        Secretaria.objects.filter(id__in=unidades_qs.values_list("secretaria_id", flat=True).distinct())
        .select_related("municipio")
        .order_by("municipio__nome", "nome")
    )


class FechamentoPeriodoLoteForm(forms.Form):
    ano_letivo = forms.IntegerField(label="Ano letivo", min_value=2000, max_value=2200)
    periodo = forms.ModelChoiceField(label="Período letivo", queryset=PeriodoLetivo.objects.none(), required=True)
    secretaria = forms.ModelChoiceField(
        label="Secretaria (opcional)",
        queryset=Secretaria.objects.none(),
        required=False,
        empty_label="Todas no escopo",
    )
    unidade = forms.ModelChoiceField(
        label="Unidade (opcional)",
        queryset=Unidade.objects.none(),
        required=False,
        empty_label="Todas no escopo",
    )
    media_corte = forms.DecimalField(label="Média de corte", max_digits=5, decimal_places=2, initial=Decimal("6.00"))
    frequencia_corte = forms.DecimalField(
        label="Frequência mínima (%)",
        max_digits=5,
        decimal_places=2,
        initial=Decimal("75.00"),
    )
    somente_com_matriculas = forms.BooleanField(
        label="Somente turmas com matrículas ativas",
        required=False,
        initial=True,
    )
    incluir_turmas_ja_fechadas = forms.BooleanField(
        label="Incluir turmas já fechadas no período",
        required=False,
    )
    observacao = forms.CharField(
        label="Observação do fechamento",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        ano_now = timezone.localdate().year
        if not self.is_bound:
            self.fields["ano_letivo"].initial = ano_now

        unidades_scope = _unidades_educacao_scope(user) if user is not None else Unidade.objects.none()
        secretarias_scope = _secretarias_from_unidades(unidades_scope)

        self.fields["secretaria"].queryset = secretarias_scope
        self.fields["unidade"].queryset = unidades_scope.order_by("nome")

        ano_ref = ano_now
        sec_raw = ""
        if self.is_bound:
            sec_raw = (self.data.get(self.add_prefix("secretaria")) or "").strip()
            ano_raw = (self.data.get(self.add_prefix("ano_letivo")) or "").strip()
            if ano_raw.isdigit():
                ano_ref = int(ano_raw)
        else:
            sec_raw = str(self.initial.get("secretaria") or "").strip()
            initial_ano = self.initial.get("ano_letivo")
            if initial_ano:
                ano_ref = int(initial_ano)

        unidades_qs = self.fields["unidade"].queryset
        if sec_raw.isdigit():
            unidades_qs = unidades_qs.filter(secretaria_id=int(sec_raw))
        self.fields["unidade"].queryset = unidades_qs
        self.fields["periodo"].queryset = PeriodoLetivo.objects.filter(ano_letivo=ano_ref, ativo=True).order_by("numero")

    def clean(self):
        cleaned = super().clean()
        periodo = cleaned.get("periodo")
        ano = cleaned.get("ano_letivo")
        if periodo and ano and periodo.ano_letivo != ano:
            self.add_error("periodo", "O período selecionado não pertence ao ano letivo informado.")
        return cleaned


def _turmas_lote_scope(user, cleaned_data: dict):
    qs = scope_filter_turmas(
        user,
        Turma.objects.select_related("unidade", "unidade__secretaria")
        .filter(
            unidade__tipo=Unidade.Tipo.EDUCACAO,
            ano_letivo=cleaned_data["ano_letivo"],
            ativo=True,
        )
        .order_by("unidade__nome", "nome"),
    )
    secretaria = cleaned_data.get("secretaria")
    unidade = cleaned_data.get("unidade")
    if secretaria is not None:
        qs = qs.filter(unidade__secretaria=secretaria)
    if unidade is not None:
        qs = qs.filter(unidade=unidade)
    return qs


def _resumo_turma_periodo(*, turma: Turma, periodo: PeriodoLetivo, media_corte: Decimal, frequencia_corte: Decimal):
    matriculas = list(
        Matricula.objects.select_related("aluno")
        .filter(turma=turma, situacao=Matricula.Situacao.ATIVA)
        .order_by("aluno__nome")
    )
    aluno_ids = [m.aluno_id for m in matriculas]
    media_map, freq_map, _ = calc_periodo_metrics_by_aluno(turma=turma, periodo=periodo, aluno_ids=aluno_ids)

    aprovados = 0
    recuperacao = 0
    reprovados = 0
    for aluno_id in aluno_ids:
        resultado = classify_resultado(
            media=media_map.get(aluno_id),
            frequencia=freq_map.get(aluno_id),
            media_corte=Decimal(str(media_corte)),
            frequencia_corte=Decimal(str(frequencia_corte)),
        )
        if resultado == "Aprovado":
            aprovados += 1
        elif resultado == "Recuperação":
            recuperacao += 1
        else:
            reprovados += 1

    return {
        "total_alunos": len(aluno_ids),
        "aprovados": aprovados,
        "recuperacao": recuperacao,
        "reprovados": reprovados,
    }


def _rows_preview(*, turmas: list[Turma], periodo: PeriodoLetivo, fechamentos_map: dict[int, FechamentoPeriodoTurma]):
    rows = []
    for turma in turmas:
        fechamento = fechamentos_map.get(turma.id)
        status = "Fechada" if fechamento else "Aberta"
        fechado_em = fechamento.fechado_em.strftime("%d/%m/%Y %H:%M") if fechamento and fechamento.fechado_em else "—"
        matriculas_ativas = Matricula.objects.filter(turma=turma, situacao=Matricula.Situacao.ATIVA).count()
        rows.append(
            {
                "cells": [
                    {"text": turma.nome},
                    {"text": turma.unidade.nome},
                    {"text": str(matriculas_ativas)},
                    {"text": status},
                    {"text": fechado_em},
                    {"text": str(periodo)},
                ]
            }
        )
    return rows


@login_required
@require_perm("educacao.manage")
def fechamento_periodo_lote(request):
    form = FechamentoPeriodoLoteForm(request.POST or None, user=request.user)
    preview_headers = [
        {"label": "Turma"},
        {"label": "Unidade"},
        {"label": "Matrículas ativas", "width": "140px"},
        {"label": "Status", "width": "120px"},
        {"label": "Fechado em", "width": "160px"},
        {"label": "Período"},
    ]
    preview_rows = []
    preview_total = 0

    if request.method == "POST" and form.is_valid():
        action = (request.POST.get("_action") or "preview").strip().lower()
        cleaned = form.cleaned_data
        periodo = cleaned["periodo"]

        turmas_qs = _turmas_lote_scope(request.user, cleaned)
        if cleaned.get("somente_com_matriculas", True):
            turmas_qs = turmas_qs.filter(matriculas__situacao=Matricula.Situacao.ATIVA).distinct()

        turmas = list(turmas_qs)
        fechamentos_map = {
            obj.turma_id: obj
            for obj in FechamentoPeriodoTurma.objects.filter(
                turma_id__in=[t.id for t in turmas],
                periodo=periodo,
            )
        }

        preview_rows = _rows_preview(turmas=turmas, periodo=periodo, fechamentos_map=fechamentos_map)
        preview_total = len(preview_rows)

        if action == "fechar":
            processadas = 0
            with transaction.atomic():
                for turma in turmas:
                    if turma.id in fechamentos_map and not cleaned.get("incluir_turmas_ja_fechadas"):
                        continue
                    resumo = _resumo_turma_periodo(
                        turma=turma,
                        periodo=periodo,
                        media_corte=cleaned["media_corte"],
                        frequencia_corte=cleaned["frequencia_corte"],
                    )
                    FechamentoPeriodoTurma.objects.update_or_create(
                        turma=turma,
                        periodo=periodo,
                        defaults={
                            "media_corte": cleaned["media_corte"],
                            "frequencia_corte": cleaned["frequencia_corte"],
                            "total_alunos": resumo["total_alunos"],
                            "aprovados": resumo["aprovados"],
                            "recuperacao": resumo["recuperacao"],
                            "reprovados": resumo["reprovados"],
                            "observacao": (cleaned.get("observacao") or "").strip(),
                            "fechado_por": request.user,
                        },
                    )
                    processadas += 1

            messages.success(request, f"Fechamento em lote concluído para {processadas} turma(s).")
            return redirect("educacao:fechamento_periodo_lote")

        if action == "reabrir":
            turmas_ids = [t.id for t in turmas]
            deleted, _ = FechamentoPeriodoTurma.objects.filter(turma_id__in=turmas_ids, periodo=periodo).delete()
            messages.success(
                request,
                f"Reabertura em lote concluída. {deleted} registro(s) de fechamento removido(s).",
            )
            return redirect("educacao:fechamento_periodo_lote")

        messages.info(request, f"Prévia gerada com {preview_total} turma(s).")

    return render(
        request,
        "educacao/fechamento_periodo_lote.html",
        {
            "form": form,
            "preview_headers": preview_headers,
            "preview_rows": preview_rows,
            "preview_total": preview_total,
            "actions": [
                {
                    "label": "Voltar para períodos",
                    "url": reverse("educacao:periodo_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                }
            ],
        },
    )
