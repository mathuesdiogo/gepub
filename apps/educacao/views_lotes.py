from __future__ import annotations

from uuid import uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.decorators import require_perm
from apps.core.rbac import scope_filter_matriculas, scope_filter_turmas, scope_filter_unidades
from apps.org.models import Secretaria, Unidade

from .models import Matricula, MatriculaMovimentacao, MatrizCurricular, Turma
from .models_periodos import PeriodoLetivo
from .services_matricula import registrar_movimentacao
from .services_turma_setup import inicializar_turma_fluxo_anual


LOTE_EVASAO_PREFIX = "[EVASAO-LOTE:"


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


def _normalizar_token_lote(raw: str) -> str:
    allowed = [ch for ch in (raw or "").strip() if ch.isalnum()]
    return "".join(allowed)[:24]


def _indice_para_sufixo(index: int) -> str:
    if index <= 0:
        return ""
    chars: list[str] = []
    value = index
    while value > 0:
        value, rem = divmod(value - 1, 26)
        chars.append(chr(65 + rem))
    return "".join(reversed(chars))


def _proximo_nome_disponivel(base_name: str, existing_names: set[str]) -> str:
    candidate = base_name.strip()
    if candidate not in existing_names:
        existing_names.add(candidate)
        return candidate
    idx = 2
    while True:
        candidate = f"{base_name.strip()} ({idx})"
        if candidate not in existing_names:
            existing_names.add(candidate)
            return candidate
        idx += 1


class TurmaGeracaoLoteForm(forms.Form):
    ano_letivo = forms.IntegerField(label="Ano letivo", min_value=2000, max_value=2200)
    periodo_letivo = forms.ModelChoiceField(
        label="Período letivo (opcional)",
        queryset=PeriodoLetivo.objects.none(),
        required=False,
        empty_label="Selecionar período",
    )
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
    matrizes = forms.ModelMultipleChoiceField(
        label="Matrizes curriculares",
        queryset=MatrizCurricular.objects.none(),
        required=True,
        widget=forms.SelectMultiple(attrs={"size": 10}),
    )
    quantidade_por_matriz = forms.IntegerField(
        label="Quantidade de turmas por matriz",
        min_value=1,
        max_value=20,
        initial=1,
    )
    turno = forms.ChoiceField(label="Turno padrão", choices=Turma.Turno.choices, initial=Turma.Turno.MANHA)
    prefixo_nome = forms.CharField(
        label="Prefixo do nome da turma",
        max_length=60,
        required=False,
        initial="Turma",
        help_text="Ex.: Turma, Classe, GNF",
    )
    gerar_horario = forms.BooleanField(label="Gerar grade horária padrão", required=False, initial=True)
    overwrite_horario = forms.BooleanField(label="Sobrescrever horário existente", required=False)
    turmas_ativas = forms.BooleanField(label="Criar turmas como ativas", required=False, initial=True)

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
        uni_raw = ""
        if self.is_bound:
            sec_raw = (self.data.get(self.add_prefix("secretaria")) or "").strip()
            uni_raw = (self.data.get(self.add_prefix("unidade")) or "").strip()
            ano_raw = (self.data.get(self.add_prefix("ano_letivo")) or "").strip()
            if ano_raw.isdigit():
                ano_ref = int(ano_raw)
        else:
            sec_raw = str(self.initial.get("secretaria") or "").strip()
            uni_raw = str(self.initial.get("unidade") or "").strip()
            initial_ano = self.initial.get("ano_letivo")
            if initial_ano:
                ano_ref = int(initial_ano)

        unidades_qs = self.fields["unidade"].queryset
        if sec_raw.isdigit():
            unidades_qs = unidades_qs.filter(secretaria_id=int(sec_raw))
        self.fields["unidade"].queryset = unidades_qs

        matrizes_qs = (
            MatrizCurricular.objects.select_related("unidade", "unidade__secretaria")
            .filter(unidade_id__in=unidades_scope.values_list("id", flat=True), ativo=True)
            .order_by("-ano_referencia", "unidade__nome", "serie_ano", "nome")
        )
        if sec_raw.isdigit():
            matrizes_qs = matrizes_qs.filter(unidade__secretaria_id=int(sec_raw))
        if uni_raw.isdigit():
            matrizes_qs = matrizes_qs.filter(unidade_id=int(uni_raw))
        self.fields["matrizes"].queryset = matrizes_qs
        self.fields["periodo_letivo"].queryset = PeriodoLetivo.objects.filter(ativo=True, ano_letivo=ano_ref).order_by(
            "numero"
        )

    def clean(self):
        cleaned = super().clean()
        periodo = cleaned.get("periodo_letivo")
        ano_letivo = cleaned.get("ano_letivo")
        if periodo and ano_letivo and periodo.ano_letivo != ano_letivo:
            self.add_error("periodo_letivo", "O período letivo precisa ser do mesmo ano informado.")
        return cleaned


class EvasaoLoteForm(forms.Form):
    ano_letivo = forms.IntegerField(label="Ano letivo", min_value=2000, max_value=2200)
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
    turma = forms.ModelChoiceField(
        label="Turma (opcional)",
        queryset=Turma.objects.none(),
        required=False,
        empty_label="Todas no escopo",
    )
    data_referencia = forms.DateField(
        label="Data de referência",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    motivo = forms.CharField(
        label="Motivo da evasão em lote",
        max_length=220,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Esse motivo ficará registrado no histórico de movimentação.",
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        if not self.is_bound:
            self.fields["ano_letivo"].initial = today.year
            self.fields["data_referencia"].initial = today

        unidades_scope = _unidades_educacao_scope(user) if user is not None else Unidade.objects.none()
        secretarias_scope = _secretarias_from_unidades(unidades_scope)
        turmas_scope = scope_filter_turmas(
            user,
            Turma.objects.select_related("unidade", "unidade__secretaria").filter(unidade__tipo=Unidade.Tipo.EDUCACAO),
        ).order_by("-ano_letivo", "nome")
        self.fields["secretaria"].queryset = secretarias_scope
        self.fields["unidade"].queryset = unidades_scope.order_by("nome")

        sec_raw = ""
        uni_raw = ""
        ano_ref = today.year
        if self.is_bound:
            sec_raw = (self.data.get(self.add_prefix("secretaria")) or "").strip()
            uni_raw = (self.data.get(self.add_prefix("unidade")) or "").strip()
            ano_raw = (self.data.get(self.add_prefix("ano_letivo")) or "").strip()
            if ano_raw.isdigit():
                ano_ref = int(ano_raw)
        else:
            sec_raw = str(self.initial.get("secretaria") or "").strip()
            uni_raw = str(self.initial.get("unidade") or "").strip()
            initial_ano = self.initial.get("ano_letivo")
            if initial_ano:
                ano_ref = int(initial_ano)

        unidades_qs = self.fields["unidade"].queryset
        if sec_raw.isdigit():
            unidades_qs = unidades_qs.filter(secretaria_id=int(sec_raw))
        self.fields["unidade"].queryset = unidades_qs

        if sec_raw.isdigit():
            turmas_scope = turmas_scope.filter(unidade__secretaria_id=int(sec_raw))
        if uni_raw.isdigit():
            turmas_scope = turmas_scope.filter(unidade_id=int(uni_raw))
        turmas_scope = turmas_scope.filter(ano_letivo=ano_ref)
        self.fields["turma"].queryset = turmas_scope

    def clean(self):
        cleaned = super().clean()
        data_ref = cleaned.get("data_referencia")
        if data_ref and data_ref > timezone.localdate():
            self.add_error("data_referencia", "A data de referência não pode ser futura.")
        return cleaned


def _dados_turma_from_matriz(matriz: MatrizCurricular) -> dict[str, str]:
    expected_etapa = Turma.expected_etapa_from_matriz(matriz) or Turma.Etapa.FUNDAMENTAL_ANOS_INICIAIS
    expected_serie = Turma.expected_serie_from_matriz(matriz) or Turma.SerieAno.NAO_APLICA
    modalidade = (
        Turma.Modalidade.EDUCACAO_INFANTIL
        if matriz.etapa_base == MatrizCurricular.EtapaBase.EDUCACAO_INFANTIL
        else Turma.Modalidade.REGULAR
    )
    return {
        "modalidade": modalidade,
        "etapa": expected_etapa,
        "serie_ano": expected_serie,
    }


def _build_turma_geracao_preview(cleaned_data: dict) -> list[dict]:
    matrizes = list(
        cleaned_data["matrizes"].select_related("unidade", "unidade__secretaria").order_by(
            "unidade__nome",
            "serie_ano",
            "nome",
        )
    )
    ano_letivo = int(cleaned_data["ano_letivo"])
    quantidade = int(cleaned_data["quantidade_por_matriz"])
    prefixo = (cleaned_data.get("prefixo_nome") or "").strip()

    existing_by_unidade: dict[int, set[str]] = {}
    preview: list[dict] = []
    for matriz in matrizes:
        unidade = matriz.unidade
        if unidade_id := getattr(unidade, "id", None):
            if unidade_id not in existing_by_unidade:
                existing_by_unidade[unidade_id] = set(
                    Turma.objects.filter(unidade_id=unidade_id, ano_letivo=ano_letivo).values_list("nome", flat=True)
                )
            existing_names = existing_by_unidade[unidade_id]
        else:
            existing_names = set()

        serie_label = matriz.get_serie_ano_display()
        base = f"{prefixo} {serie_label}".strip() if prefixo else serie_label
        for idx in range(1, quantidade + 1):
            sufixo = _indice_para_sufixo(idx) if quantidade > 1 else ""
            desired_name = f"{base} {sufixo}".strip()
            generated_name = _proximo_nome_disponivel(desired_name, existing_names)
            defaults = _dados_turma_from_matriz(matriz)
            preview.append(
                {
                    "matriz": matriz,
                    "unidade": unidade,
                    "nome_turma": generated_name,
                    "modalidade": defaults["modalidade"],
                    "etapa": defaults["etapa"],
                    "serie_ano": defaults["serie_ano"],
                }
            )
    return preview


def _render_rows_preview_turmas(preview: list[dict], *, ano_letivo: int, turno: str) -> list[dict]:
    rows: list[dict] = []
    for item in preview:
        matriz: MatrizCurricular = item["matriz"]
        unidade: Unidade = item["unidade"]
        rows.append(
            {
                "cells": [
                    {"text": item["nome_turma"]},
                    {"text": getattr(unidade, "nome", "—")},
                    {"text": getattr(getattr(unidade, "secretaria", None), "nome", "—")},
                    {"text": matriz.nome},
                    {"text": str(ano_letivo)},
                    {"text": dict(Turma.Turno.choices).get(turno, turno)},
                    {"text": dict(Turma.Modalidade.choices).get(item["modalidade"], item["modalidade"])},
                ]
            }
        )
    return rows


def _query_matriculas_evasao(user, cleaned_data: dict):
    qs = (
        Matricula.objects.select_related(
            "aluno",
            "turma",
            "turma__unidade",
            "turma__unidade__secretaria",
        )
        .filter(
            turma__ano_letivo=cleaned_data["ano_letivo"],
            situacao=Matricula.Situacao.ATIVA,
        )
        .order_by("turma__nome", "aluno__nome")
    )
    qs = scope_filter_matriculas(user, qs)

    secretaria = cleaned_data.get("secretaria")
    unidade = cleaned_data.get("unidade")
    turma = cleaned_data.get("turma")
    if secretaria is not None:
        qs = qs.filter(turma__unidade__secretaria=secretaria)
    if unidade is not None:
        qs = qs.filter(turma__unidade=unidade)
    if turma is not None:
        qs = qs.filter(turma=turma)
    return qs


def _render_rows_preview_evasao(matriculas: list[Matricula]) -> list[dict]:
    rows: list[dict] = []
    for matricula in matriculas:
        turma = matricula.turma
        unidade = getattr(turma, "unidade", None)
        rows.append(
            {
                "cells": [
                    {"text": matricula.aluno.nome},
                    {"text": getattr(turma, "nome", "—")},
                    {"text": getattr(unidade, "nome", "—")},
                    {"text": matricula.get_situacao_display()},
                    {"text": matricula.data_matricula.strftime("%d/%m/%Y") if matricula.data_matricula else "—"},
                ]
            }
        )
    return rows


@login_required
@require_perm("educacao.manage")
def turma_geracao_lote(request):
    form = TurmaGeracaoLoteForm(request.POST or None, user=request.user)
    preview_rows: list[dict] = []
    preview_total = 0
    preview_headers = [
        {"label": "Turma planejada"},
        {"label": "Unidade"},
        {"label": "Secretaria"},
        {"label": "Matriz curricular"},
        {"label": "Ano"},
        {"label": "Turno"},
        {"label": "Modalidade"},
    ]

    if request.method == "POST" and form.is_valid():
        action = (request.POST.get("_action") or "preview").strip().lower()
        cleaned = form.cleaned_data
        preview = _build_turma_geracao_preview(cleaned)
        preview_total = len(preview)
        preview_rows = _render_rows_preview_turmas(
            preview,
            ano_letivo=int(cleaned["ano_letivo"]),
            turno=cleaned["turno"],
        )

        if action == "execute":
            if not preview:
                messages.warning(request, "Nenhuma turma foi planejada para os filtros informados.")
                return redirect("educacao:turma_geracao_lote")

            total_criadas = 0
            diarios_criados = 0
            horarios_criados = 0
            with transaction.atomic():
                for item in preview:
                    defaults = _dados_turma_from_matriz(item["matriz"])
                    turma = Turma(
                        unidade=item["unidade"],
                        nome=item["nome_turma"],
                        ano_letivo=cleaned["ano_letivo"],
                        turno=cleaned["turno"],
                        modalidade=defaults["modalidade"],
                        etapa=defaults["etapa"],
                        serie_ano=defaults["serie_ano"],
                        matriz_curricular=item["matriz"],
                        ativo=bool(cleaned.get("turmas_ativas", True)),
                    )
                    turma.full_clean()
                    turma.save()
                    total_criadas += 1
                    setup_result = inicializar_turma_fluxo_anual(
                        turma,
                        overwrite_horario=bool(cleaned.get("overwrite_horario")),
                        gerar_horario=bool(cleaned.get("gerar_horario", True)),
                    )
                    diarios_criados += int(setup_result.diarios.criados or 0)
                    horarios_criados += int(setup_result.horario.criado or 0)

            messages.success(
                request,
                (
                    f"Geração concluída: {total_criadas} turma(s) criada(s), "
                    f"{diarios_criados} diário(s) novo(s) e {horarios_criados} horário(s) criado(s)."
                ),
            )
            return redirect("educacao:turma_list")

        messages.info(request, f"Prévia gerada com {preview_total} turma(s) planejada(s).")

    return render(
        request,
        "educacao/turma_geracao_lote.html",
        {
            "form": form,
            "preview_headers": preview_headers,
            "preview_rows": preview_rows,
            "preview_total": preview_total,
            "actions": [
                {
                    "label": "Voltar para turmas",
                    "url": reverse("educacao:turma_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                }
            ],
        },
    )


@login_required
@require_perm("educacao.manage")
def evasao_lote(request):
    form = EvasaoLoteForm(request.POST or None, user=request.user)
    preview_headers = [
        {"label": "Aluno"},
        {"label": "Turma"},
        {"label": "Unidade"},
        {"label": "Situação atual"},
        {"label": "Matrícula"},
    ]
    preview_rows: list[dict] = []
    preview_total = 0
    ultimo_token = _normalizar_token_lote((request.GET.get("token") or "").strip())

    if request.method == "POST":
        action = (request.POST.get("_action") or "preview").strip().lower()

        if action == "rollback":
            rollback_token = _normalizar_token_lote(request.POST.get("rollback_token") or "")
            if not rollback_token:
                messages.error(request, "Token de rollback inválido.")
                return redirect("educacao:evasao_lote")

            movimentos = list(
                MatriculaMovimentacao.objects.select_related("matricula", "turma_origem", "turma_destino")
                .filter(
                    tipo=MatriculaMovimentacao.Tipo.SITUACAO,
                    motivo__contains=f"{LOTE_EVASAO_PREFIX}{rollback_token}]",
                )
                .order_by("-criado_em", "-id")
            )
            if not movimentos:
                messages.warning(request, "Nenhum movimento encontrado para o token informado.")
                return redirect("educacao:evasao_lote")

            restaurados = 0
            conflitos = 0
            with transaction.atomic():
                for mov in movimentos:
                    matricula = mov.matricula
                    ultimo_mov = (
                        MatriculaMovimentacao.objects.filter(matricula=matricula)
                        .exclude(tipo=MatriculaMovimentacao.Tipo.CRIACAO)
                        .exclude(tipo=MatriculaMovimentacao.Tipo.DESFAZER)
                        .order_by("-criado_em", "-id")
                        .first()
                    )
                    if ultimo_mov is None or ultimo_mov.id != mov.id:
                        conflitos += 1
                        continue

                    situacao_anterior = mov.situacao_anterior or Matricula.Situacao.ATIVA
                    turma_ref = mov.turma_origem or matricula.turma
                    situacao_atual = matricula.situacao

                    if matricula.situacao != situacao_anterior:
                        matricula.situacao = situacao_anterior
                        matricula.save(update_fields=["situacao"])

                    registrar_movimentacao(
                        matricula=matricula,
                        tipo=MatriculaMovimentacao.Tipo.DESFAZER,
                        usuario=request.user,
                        turma_origem=matricula.turma,
                        turma_destino=turma_ref,
                        situacao_anterior=situacao_atual,
                        situacao_nova=matricula.situacao,
                        data_referencia=mov.data_referencia,
                        movimentacao_desfeita=mov,
                        motivo=f"Rollback seguro do lote de evasão {rollback_token}.",
                    )
                    restaurados += 1

            if restaurados:
                messages.success(
                    request,
                    f"Rollback concluído: {restaurados} matrícula(s) restaurada(s).",
                )
            if conflitos:
                messages.warning(
                    request,
                    (
                        f"{conflitos} item(ns) não puderam ser desfeitos porque a matrícula "
                        "recebeu novos procedimentos após o lote."
                    ),
                )
            return redirect("educacao:evasao_lote")

        if form.is_valid():
            cleaned = form.cleaned_data
            matriculas = list(_query_matriculas_evasao(request.user, cleaned))
            preview_total = len(matriculas)
            preview_rows = _render_rows_preview_evasao(matriculas)

            if action == "execute":
                if not matriculas:
                    messages.warning(request, "Nenhuma matrícula ativa encontrada para os filtros informados.")
                    return redirect("educacao:evasao_lote")

                lote_token = _normalizar_token_lote(uuid4().hex[:12])
                motivo_base = (cleaned["motivo"] or "").strip()
                motivo_lote = f"{LOTE_EVASAO_PREFIX}{lote_token}] {motivo_base}".strip()
                alteradas = 0
                with transaction.atomic():
                    for matricula in matriculas:
                        if matricula.situacao != Matricula.Situacao.ATIVA:
                            continue
                        situacao_anterior = matricula.situacao
                        matricula.situacao = Matricula.Situacao.EVADIDO
                        matricula.save(update_fields=["situacao"])
                        registrar_movimentacao(
                            matricula=matricula,
                            tipo=MatriculaMovimentacao.Tipo.SITUACAO,
                            usuario=request.user,
                            turma_origem=matricula.turma,
                            turma_destino=matricula.turma,
                            situacao_anterior=situacao_anterior,
                            situacao_nova=matricula.situacao,
                            data_referencia=cleaned["data_referencia"],
                            motivo=motivo_lote,
                        )
                        alteradas += 1

                messages.success(
                    request,
                    (
                        f"Evasão em lote aplicada em {alteradas} matrícula(s). "
                        f"Token para rollback seguro: {lote_token}"
                    ),
                )
                return redirect(f"{reverse('educacao:evasao_lote')}?token={lote_token}")

            messages.info(request, f"Prévia pronta com {preview_total} matrícula(s) elegível(is).")

    return render(
        request,
        "educacao/evasao_lote.html",
        {
            "form": form,
            "preview_headers": preview_headers,
            "preview_rows": preview_rows,
            "preview_total": preview_total,
            "ultimo_token": ultimo_token,
            "actions": [
                {
                    "label": "Voltar para alunos",
                    "url": reverse("educacao:aluno_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                }
            ],
        },
    )
