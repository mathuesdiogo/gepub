from __future__ import annotations

from collections import defaultdict

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.decorators import require_perm
from apps.core.rbac import scope_filter_secretarias, scope_filter_turmas
from apps.core.services_auditoria import registrar_auditoria
from apps.core.services_transparencia import publicar_evento_transparencia
from apps.org.models import Secretaria
from apps.processos.models import ProcessoAdministrativo, ProcessoAndamento

from .models import (
    Matricula,
    MatriculaMovimentacao,
    RenovacaoMatricula,
    RenovacaoMatriculaOferta,
    RenovacaoMatriculaPedido,
    Turma,
)
from .models_periodos import PeriodoLetivo
from .services_matricula import aplicar_movimentacao_matricula, registrar_movimentacao


class RenovacaoMatriculaForm(forms.Form):
    descricao = forms.CharField(label="Descrição", max_length=220)
    ano_letivo = forms.IntegerField(label="Ano letivo", min_value=2000, max_value=2100)
    periodo_letivo = forms.ModelChoiceField(
        label="Período letivo",
        queryset=PeriodoLetivo.objects.none(),
        required=False,
        empty_label="Selecione (opcional)",
    )
    secretaria = forms.ModelChoiceField(
        label="Secretaria",
        queryset=Secretaria.objects.none(),
    )
    data_inicio = forms.DateField(label="Início", widget=forms.DateInput(attrs={"type": "date"}))
    data_fim = forms.DateField(label="Fim", widget=forms.DateInput(attrs={"type": "date"}))
    observacao = forms.CharField(
        label="Observação",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["secretaria"].queryset = scope_filter_secretarias(
                user,
                Secretaria.objects.select_related("municipio").order_by("municipio__nome", "nome"),
            )
        self.fields["periodo_letivo"].queryset = PeriodoLetivo.objects.filter(ativo=True).order_by("-ano_letivo", "-numero")

    def clean(self):
        cleaned = super().clean()
        data_inicio = cleaned.get("data_inicio")
        data_fim = cleaned.get("data_fim")
        periodo = cleaned.get("periodo_letivo")
        ano_letivo = cleaned.get("ano_letivo")

        if data_inicio and data_fim and data_fim < data_inicio:
            self.add_error("data_fim", "A data de término deve ser igual ou posterior à data de início.")
        if periodo and ano_letivo and periodo.ano_letivo != ano_letivo:
            self.add_error("periodo_letivo", "O período letivo precisa ser do mesmo ano da renovação.")
        return cleaned


class RenovacaoOfertaForm(forms.Form):
    turma = forms.ModelChoiceField(
        label="Turma ofertada",
        queryset=Turma.objects.none(),
    )
    observacao = forms.CharField(
        label="Observação",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args, user=None, renovacao: RenovacaoMatricula | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Turma.objects.none()
        if user is not None:
            qs = scope_filter_turmas(
                user,
                Turma.objects.select_related("unidade", "unidade__secretaria").filter(ativo=True),
            )
        if renovacao is not None:
            qs = qs.filter(
                unidade__secretaria_id=renovacao.secretaria_id,
                ano_letivo=renovacao.ano_letivo,
            )
        self.fields["turma"].queryset = qs.order_by("nome")


class RenovacaoPedidoAlunoForm(forms.Form):
    oferta_id = forms.IntegerField(required=True)
    prioridade = forms.IntegerField(required=True, min_value=1, max_value=6)
    observacao_aluno = forms.CharField(required=False, max_length=500)


def _renovacoes_scope(user):
    secretarias_qs = scope_filter_secretarias(
        user,
        Secretaria.objects.all(),
    )
    return (
        RenovacaoMatricula.objects.select_related("secretaria", "secretaria__municipio", "periodo_letivo", "processado_por")
        .filter(secretaria__in=secretarias_qs)
        .annotate(
            ofertas_total=Count("ofertas", distinct=True),
            pedidos_total=Count("pedidos", distinct=True),
            pedidos_pendentes=Count(
                "pedidos",
                filter=Q(pedidos__status=RenovacaoMatriculaPedido.Status.PENDENTE),
                distinct=True,
            ),
            pedidos_aprovados=Count(
                "pedidos",
                filter=Q(pedidos__status=RenovacaoMatriculaPedido.Status.APROVADO),
                distinct=True,
            ),
            pedidos_rejeitados=Count(
                "pedidos",
                filter=Q(pedidos__status=RenovacaoMatriculaPedido.Status.REJEITADO),
                distinct=True,
            ),
        )
        .order_by("-ano_letivo", "-data_inicio", "-id")
    )


def _status_badge_class(etapa: str) -> str:
    return {
        RenovacaoMatricula.Etapa.AGENDADA: "warning",
        RenovacaoMatricula.Etapa.AGUARDANDO_MATRICULA: "primary",
        RenovacaoMatricula.Etapa.AGUARDANDO_PROCESSAMENTO: "danger",
        RenovacaoMatricula.Etapa.PROCESSADA: "success",
        RenovacaoMatricula.Etapa.INATIVA: "muted",
    }.get(etapa, "muted")


def _registrar_auditoria_renovacao(
    *,
    renovacao: RenovacaoMatricula,
    evento: str,
    usuario=None,
    antes: dict | None = None,
    depois: dict | None = None,
    observacao: str = "",
):
    municipio = getattr(getattr(renovacao, "secretaria", None), "municipio", None)
    if municipio is None:
        return
    registrar_auditoria(
        municipio=municipio,
        modulo="EDUCACAO",
        evento=evento,
        entidade="RenovacaoMatricula",
        entidade_id=renovacao.pk,
        usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
        antes=antes or {},
        depois=depois or {},
        observacao=observacao,
    )


def _publicar_evento_renovacao(
    *,
    renovacao: RenovacaoMatricula,
    tipo_evento: str,
    titulo: str,
    descricao: str = "",
    dados: dict | None = None,
):
    municipio = getattr(getattr(renovacao, "secretaria", None), "municipio", None)
    if municipio is None:
        return
    payload = {
        "contexto": "EDUCACAO_RENOVACAO",
        "renovacao_id": renovacao.pk,
        "secretaria_id": renovacao.secretaria_id,
        "ano_letivo": renovacao.ano_letivo,
    }
    if dados:
        payload.update(dados)
    publicar_evento_transparencia(
        municipio=municipio,
        modulo="OUTROS",
        tipo_evento=tipo_evento,
        titulo=titulo,
        descricao=descricao,
        referencia=f"RENOVACAO-{renovacao.pk}",
        dados=payload,
        publico=True,
    )


def _resolver_origem_matricula(aluno, renovacao: RenovacaoMatricula):
    return (
        Matricula.objects.select_related("turma")
        .filter(
            aluno=aluno,
            turma__ano_letivo=renovacao.ano_letivo,
        )
        .order_by(
            "-situacao",
            "-id",
        )
        .first()
    )


def _garantir_matricula_destino(*, pedido: RenovacaoMatriculaPedido, usuario):
    aluno = pedido.aluno
    renovacao = pedido.renovacao
    turma_destino = pedido.oferta.turma
    hoje = timezone.localdate()

    existente_mesma_turma = Matricula.objects.filter(aluno=aluno, turma=turma_destino).order_by("-id").first()
    if existente_mesma_turma:
        if existente_mesma_turma.situacao != Matricula.Situacao.ATIVA:
            try:
                aplicar_movimentacao_matricula(
                    matricula=existente_mesma_turma,
                    tipo=MatriculaMovimentacao.Tipo.REATIVACAO,
                    usuario=usuario,
                    data_referencia=hoje,
                    motivo=f"Reativação automática por renovação: {renovacao.descricao}",
                )
            except ValueError:
                situacao_anterior = existente_mesma_turma.situacao
                existente_mesma_turma.situacao = Matricula.Situacao.ATIVA
                existente_mesma_turma.save(update_fields=["situacao"])
                registrar_movimentacao(
                    matricula=existente_mesma_turma,
                    tipo=MatriculaMovimentacao.Tipo.REATIVACAO,
                    usuario=usuario,
                    turma_origem=turma_destino,
                    turma_destino=turma_destino,
                    situacao_anterior=situacao_anterior,
                    situacao_nova=Matricula.Situacao.ATIVA,
                    data_referencia=hoje,
                    motivo=f"Reativação automática por renovação: {renovacao.descricao}",
                )
        return existente_mesma_turma

    matricula_ativa_ano = (
        Matricula.objects.select_related("turma")
        .filter(
            aluno=aluno,
            turma__ano_letivo=renovacao.ano_letivo,
            situacao=Matricula.Situacao.ATIVA,
        )
        .exclude(turma=turma_destino)
        .order_by("-id")
        .first()
    )
    if matricula_ativa_ano:
        aplicar_movimentacao_matricula(
            matricula=matricula_ativa_ano,
            tipo=MatriculaMovimentacao.Tipo.REMANEJAMENTO,
            usuario=usuario,
            turma_destino=turma_destino,
            data_referencia=hoje,
            motivo=f"Remanejamento automático por renovação: {renovacao.descricao}",
        )
        matricula_ativa_ano.refresh_from_db()
        return matricula_ativa_ano

    nova_matricula = Matricula.objects.create(
        aluno=aluno,
        turma=turma_destino,
        data_matricula=hoje,
        situacao=Matricula.Situacao.ATIVA,
        observacao=f"Matrícula criada automaticamente por renovação: {renovacao.descricao}",
    )
    registrar_movimentacao(
        matricula=nova_matricula,
        tipo=MatriculaMovimentacao.Tipo.CRIACAO,
        usuario=usuario,
        turma_destino=turma_destino,
        situacao_nova=Matricula.Situacao.ATIVA,
        data_referencia=hoje,
        motivo=f"Criação automática por renovação: {renovacao.descricao}",
    )
    return nova_matricula


def _sincronizar_processo_pedido(*, pedido: RenovacaoMatriculaPedido, aprovado: bool, usuario=None):
    processo = pedido.processo_administrativo
    if processo is None:
        return

    novo_status = ProcessoAdministrativo.Status.CONCLUIDO if aprovado else ProcessoAdministrativo.Status.ARQUIVADO
    if processo.status != novo_status:
        processo.status = novo_status
        processo.save(update_fields=["status", "atualizado_em"])

    despacho = (
        f"Renovação '{pedido.renovacao.descricao}' processada. "
        f"Turma selecionada: {pedido.oferta.turma.nome}. "
        f"Resultado: {'aprovado' if aprovado else 'rejeitado'}."
    )
    if pedido.observacao_processamento:
        despacho = f"{despacho} {pedido.observacao_processamento}"
    ProcessoAndamento.objects.create(
        processo=processo,
        tipo=ProcessoAndamento.Tipo.CONCLUSAO,
        despacho=despacho[:1000],
        data_evento=timezone.localdate(),
        criado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
    )


@transaction.atomic
def _processar_pedidos_renovacao(renovacao: RenovacaoMatricula, usuario):
    pendentes = list(
        RenovacaoMatriculaPedido.objects.select_related("aluno", "oferta", "oferta__turma", "renovacao", "processo_administrativo")
        .filter(renovacao=renovacao, status=RenovacaoMatriculaPedido.Status.PENDENTE)
        .order_by("aluno_id", "prioridade", "criado_em", "id")
    )

    if not pendentes:
        renovacao.processado_em = timezone.now()
        renovacao.processado_por = usuario if getattr(usuario, "is_authenticated", False) else None
        renovacao.save(update_fields=["processado_em", "processado_por", "atualizado_em"])
        return {"total": 0, "aprovados": 0, "rejeitados": 0}

    pedidos_por_aluno: dict[int, list[RenovacaoMatriculaPedido]] = defaultdict(list)
    for pedido in pendentes:
        pedidos_por_aluno[pedido.aluno_id].append(pedido)

    aprovados = 0
    rejeitados = 0

    for _, pedidos in pedidos_por_aluno.items():
        pedidos.sort(key=lambda p: (p.prioridade, p.criado_em, p.id))
        pedido_escolhido = next((p for p in pedidos if p.oferta.ativo), None)

        if pedido_escolhido is None:
            for pedido in pedidos:
                pedido.status = RenovacaoMatriculaPedido.Status.REJEITADO
                pedido.observacao_processamento = "Pedido rejeitado: oferta indisponível para processamento."
                pedido.processado_em = timezone.now()
                pedido.processado_por = usuario if getattr(usuario, "is_authenticated", False) else None
                pedido.save(
                    update_fields=[
                        "status",
                        "observacao_processamento",
                        "processado_em",
                        "processado_por",
                        "atualizado_em",
                    ]
                )
                _sincronizar_processo_pedido(pedido=pedido, aprovado=False, usuario=usuario)
                rejeitados += 1
            continue

        matricula_resultante = _garantir_matricula_destino(
            pedido=pedido_escolhido,
            usuario=usuario,
        )
        pedido_escolhido.status = RenovacaoMatriculaPedido.Status.APROVADO
        pedido_escolhido.observacao_processamento = "Pedido aprovado e matrícula processada automaticamente."
        pedido_escolhido.processado_em = timezone.now()
        pedido_escolhido.processado_por = usuario if getattr(usuario, "is_authenticated", False) else None
        pedido_escolhido.matricula_resultante = matricula_resultante
        pedido_escolhido.save(
            update_fields=[
                "status",
                "observacao_processamento",
                "processado_em",
                "processado_por",
                "matricula_resultante",
                "atualizado_em",
            ]
        )
        _sincronizar_processo_pedido(pedido=pedido_escolhido, aprovado=True, usuario=usuario)
        aprovados += 1

        for pedido in pedidos:
            if pedido.pk == pedido_escolhido.pk:
                continue
            pedido.status = RenovacaoMatriculaPedido.Status.REJEITADO
            pedido.observacao_processamento = (
                "Pedido não contemplado: o sistema considerou a prioridade mais alta do aluno nesta renovação."
            )
            pedido.processado_em = timezone.now()
            pedido.processado_por = usuario if getattr(usuario, "is_authenticated", False) else None
            pedido.save(
                update_fields=[
                    "status",
                    "observacao_processamento",
                    "processado_em",
                    "processado_por",
                    "atualizado_em",
                ]
            )
            _sincronizar_processo_pedido(pedido=pedido, aprovado=False, usuario=usuario)
            rejeitados += 1

    renovacao.processado_em = timezone.now()
    renovacao.processado_por = usuario if getattr(usuario, "is_authenticated", False) else None
    renovacao.save(update_fields=["processado_em", "processado_por", "atualizado_em"])

    return {
        "total": len(pendentes),
        "aprovados": aprovados,
        "rejeitados": rejeitados,
    }


@login_required
@require_perm("educacao.manage")
def renovacao_matricula_list(request):
    hoje = timezone.localdate()
    stage_filter = (request.GET.get("etapa") or "TODAS").strip().upper()
    ano_filtro = (request.GET.get("ano") or "").strip()

    qs = _renovacoes_scope(request.user)
    if ano_filtro.isdigit():
        qs = qs.filter(ano_letivo=int(ano_filtro))

    form = RenovacaoMatriculaForm(request.POST or None, user=request.user, initial={"ano_letivo": hoje.year})

    if request.method == "POST" and (request.POST.get("_action") or "") == "create":
        if form.is_valid():
            renovacao = RenovacaoMatricula.objects.create(
                descricao=form.cleaned_data["descricao"],
                ano_letivo=form.cleaned_data["ano_letivo"],
                periodo_letivo=form.cleaned_data.get("periodo_letivo"),
                secretaria=form.cleaned_data["secretaria"],
                data_inicio=form.cleaned_data["data_inicio"],
                data_fim=form.cleaned_data["data_fim"],
                observacao=form.cleaned_data.get("observacao") or "",
                criado_por=request.user if request.user.is_authenticated else None,
            )
            _registrar_auditoria_renovacao(
                renovacao=renovacao,
                evento="RENOVACAO_CRIADA",
                usuario=request.user,
                depois={
                    "descricao": renovacao.descricao,
                    "ano_letivo": renovacao.ano_letivo,
                    "secretaria_id": renovacao.secretaria_id,
                    "data_inicio": str(renovacao.data_inicio),
                    "data_fim": str(renovacao.data_fim),
                    "ativo": renovacao.ativo,
                },
                observacao="Renovação criada no painel da secretaria.",
            )
            _publicar_evento_renovacao(
                renovacao=renovacao,
                tipo_evento="RENOVACAO_CRIADA",
                titulo=f"Renovação de matrícula criada: {renovacao.descricao}",
                descricao=(
                    f"Janela de renovação da secretaria {renovacao.secretaria.nome} "
                    f"para o ano letivo {renovacao.ano_letivo}."
                ),
                dados={
                    "data_inicio": str(renovacao.data_inicio),
                    "data_fim": str(renovacao.data_fim),
                },
            )
            messages.success(request, "Configuração de renovação criada com sucesso.")
            return redirect("educacao:renovacao_matricula_detail", pk=renovacao.pk)
        messages.error(request, "Corrija os erros para criar a renovação.")

    all_items = list(qs)
    for item in all_items:
        item.etapa_atual_codigo = item.etapa_atual()
        item.etapa_atual_label = item.etapa_display
        item.etapa_badge = _status_badge_class(item.etapa_atual_codigo)

    etapas_validas = {
        RenovacaoMatricula.Etapa.AGENDADA,
        RenovacaoMatricula.Etapa.AGUARDANDO_MATRICULA,
        RenovacaoMatricula.Etapa.AGUARDANDO_PROCESSAMENTO,
        RenovacaoMatricula.Etapa.PROCESSADA,
        RenovacaoMatricula.Etapa.INATIVA,
    }

    stage_totals = {k: 0 for k in etapas_validas}
    for item in all_items:
        stage_totals[item.etapa_atual_codigo] = stage_totals.get(item.etapa_atual_codigo, 0) + 1

    if stage_filter in etapas_validas:
        items = [item for item in all_items if item.etapa_atual_codigo == stage_filter]
    else:
        stage_filter = "TODAS"
        items = all_items

    rows = []
    for item in items:
        rows.append(
            {
                "cells": [
                    {
                        "text": item.descricao,
                        "url": reverse("educacao:renovacao_matricula_detail", args=[item.pk]),
                    },
                    {"text": str(item.ano_letivo)},
                    {"text": item.secretaria.nome},
                    {
                        "text": (
                            f"{item.data_inicio:%d/%m/%Y} até {item.data_fim:%d/%m/%Y}"
                        )
                    },
                    {"html": f'<span class="badge badge--{item.etapa_badge}">{item.etapa_atual_label}</span>'},
                    {"text": str(item.ofertas_total)},
                    {"text": str(item.pedidos_total)},
                    {
                        "text": (
                            f"P: {item.pedidos_pendentes} • "
                            f"A: {item.pedidos_aprovados} • "
                            f"R: {item.pedidos_rejeitados}"
                        )
                    },
                ]
            }
        )

    actions = [
        {
            "label": "Voltar",
            "url": reverse("educacao:index"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }
    ]

    etapas = [
        {
            "code": "TODAS",
            "label": "Todas",
            "count": len(all_items),
        },
        {
            "code": RenovacaoMatricula.Etapa.AGENDADA,
            "label": "Agendadas",
            "count": stage_totals.get(RenovacaoMatricula.Etapa.AGENDADA, 0),
        },
        {
            "code": RenovacaoMatricula.Etapa.AGUARDANDO_MATRICULA,
            "label": "Aguardando matrícula",
            "count": stage_totals.get(RenovacaoMatricula.Etapa.AGUARDANDO_MATRICULA, 0),
        },
        {
            "code": RenovacaoMatricula.Etapa.AGUARDANDO_PROCESSAMENTO,
            "label": "Aguardando processamento",
            "count": stage_totals.get(RenovacaoMatricula.Etapa.AGUARDANDO_PROCESSAMENTO, 0),
        },
        {
            "code": RenovacaoMatricula.Etapa.PROCESSADA,
            "label": "Processadas",
            "count": stage_totals.get(RenovacaoMatricula.Etapa.PROCESSADA, 0),
        },
        {
            "code": RenovacaoMatricula.Etapa.INATIVA,
            "label": "Inativas",
            "count": stage_totals.get(RenovacaoMatricula.Etapa.INATIVA, 0),
        },
    ]

    return render(
        request,
        "educacao/renovacao_matricula_list.html",
        {
            "actions": actions,
            "form": form,
            "rows": rows,
            "headers": [
                {"label": "Descrição"},
                {"label": "Ano", "width": "90px"},
                {"label": "Secretaria"},
                {"label": "Janela", "width": "220px"},
                {"label": "Etapa", "width": "190px"},
                {"label": "Ofertas", "width": "90px"},
                {"label": "Pedidos", "width": "90px"},
                {"label": "Status pedidos", "width": "220px"},
            ],
            "etapas": etapas,
            "stage_filter": stage_filter,
            "ano_filtro": ano_filtro,
            "action_url": reverse("educacao:renovacao_matricula_list"),
            "clear_url": reverse("educacao:renovacao_matricula_list"),
        },
    )


@login_required
@require_perm("educacao.manage")
def renovacao_matricula_detail(request, pk: int):
    renovacao = get_object_or_404(_renovacoes_scope(request.user), pk=pk)

    if request.method == "POST":
        action = (request.POST.get("_action") or "").strip()

        if action == "add_oferta":
            oferta_form = RenovacaoOfertaForm(request.POST, user=request.user, renovacao=renovacao)
            if oferta_form.is_valid():
                oferta = RenovacaoMatriculaOferta(
                    renovacao=renovacao,
                    turma=oferta_form.cleaned_data["turma"],
                    observacao=oferta_form.cleaned_data.get("observacao") or "",
                )
                try:
                    oferta.full_clean()
                    oferta.save()
                except Exception as exc:
                    messages.error(request, f"Não foi possível adicionar a oferta: {exc}")
                else:
                    _registrar_auditoria_renovacao(
                        renovacao=renovacao,
                        evento="RENOVACAO_OFERTA_ADICIONADA",
                        usuario=request.user,
                        depois={
                            "oferta_id": oferta.id,
                            "turma_id": oferta.turma_id,
                            "turma_nome": oferta.turma.nome,
                            "oferta_ativa": oferta.ativo,
                        },
                        observacao="Turma adicionada à oferta de renovação.",
                    )
                    messages.success(request, "Turma adicionada na oferta de renovação.")
                return redirect("educacao:renovacao_matricula_detail", pk=renovacao.pk)
            messages.error(request, "Corrija os erros para adicionar a oferta.")
        elif action == "remove_oferta":
            oferta_id = (request.POST.get("oferta_id") or "").strip()
            if oferta_id.isdigit():
                oferta = RenovacaoMatriculaOferta.objects.filter(renovacao=renovacao, pk=int(oferta_id)).first()
                if oferta:
                    oferta_info = {
                        "oferta_id": oferta.id,
                        "turma_id": oferta.turma_id,
                        "turma_nome": oferta.turma.nome,
                    }
                    oferta.delete()
                    _registrar_auditoria_renovacao(
                        renovacao=renovacao,
                        evento="RENOVACAO_OFERTA_REMOVIDA",
                        usuario=request.user,
                        antes=oferta_info,
                        observacao="Turma removida da oferta de renovação.",
                    )
                    messages.success(request, "Oferta removida da renovação.")
                    return redirect("educacao:renovacao_matricula_detail", pk=renovacao.pk)
        elif action == "processar":
            try:
                resultado = _processar_pedidos_renovacao(renovacao, request.user)
            except Exception as exc:
                messages.error(request, f"Erro ao processar pedidos: {exc}")
            else:
                _registrar_auditoria_renovacao(
                    renovacao=renovacao,
                    evento="RENOVACAO_PROCESSADA",
                    usuario=request.user,
                    depois={
                        "total": resultado["total"],
                        "aprovados": resultado["aprovados"],
                        "rejeitados": resultado["rejeitados"],
                        "processado_em": str(renovacao.processado_em or ""),
                    },
                    observacao="Processamento automático de pedidos executado.",
                )
                _publicar_evento_renovacao(
                    renovacao=renovacao,
                    tipo_evento="RENOVACAO_PROCESSADA",
                    titulo=f"Renovação processada: {renovacao.descricao}",
                    descricao=(
                        "Processamento automático de pedidos de renovação concluído "
                        f"na secretaria {renovacao.secretaria.nome}."
                    ),
                    dados={
                        "total_pedidos_processados": resultado["total"],
                        "total_aprovados": resultado["aprovados"],
                        "total_rejeitados": resultado["rejeitados"],
                    },
                )
                messages.success(
                    request,
                    (
                        f"Processamento concluído. "
                        f"Total: {resultado['total']} | "
                        f"Aprovados: {resultado['aprovados']} | "
                        f"Rejeitados: {resultado['rejeitados']}"
                    ),
                )
            return redirect("educacao:renovacao_matricula_detail", pk=renovacao.pk)
        elif action == "toggle_ativo":
            ativo_anterior = renovacao.ativo
            renovacao.ativo = not renovacao.ativo
            renovacao.save(update_fields=["ativo", "atualizado_em"])
            _registrar_auditoria_renovacao(
                renovacao=renovacao,
                evento="RENOVACAO_STATUS_ALTERADO",
                usuario=request.user,
                antes={"ativo": ativo_anterior},
                depois={"ativo": renovacao.ativo},
                observacao="Ativação/inativação manual da renovação.",
            )
            messages.success(request, "Status de ativação atualizado.")
            return redirect("educacao:renovacao_matricula_detail", pk=renovacao.pk)
    else:
        oferta_form = RenovacaoOfertaForm(user=request.user, renovacao=renovacao)

    ofertas = list(
        RenovacaoMatriculaOferta.objects.select_related("turma", "turma__unidade")
        .filter(renovacao=renovacao)
        .order_by("turma__nome", "id")
    )
    for oferta in ofertas:
        oferta.matriculados_ativos = Matricula.objects.filter(
            turma=oferta.turma,
            situacao=Matricula.Situacao.ATIVA,
        ).count()

    pedidos = list(
        RenovacaoMatriculaPedido.objects.select_related(
            "aluno",
            "oferta",
            "oferta__turma",
            "origem_matricula",
            "matricula_resultante",
            "processado_por",
            "processo_administrativo",
        )
        .filter(renovacao=renovacao)
        .order_by("aluno__nome", "prioridade", "id")
    )

    etapa_codigo = renovacao.etapa_atual()
    etapa_label = renovacao.etapa_display
    pendentes = sum(1 for p in pedidos if p.status == RenovacaoMatriculaPedido.Status.PENDENTE)
    aprovados = sum(1 for p in pedidos if p.status == RenovacaoMatriculaPedido.Status.APROVADO)
    rejeitados = sum(1 for p in pedidos if p.status == RenovacaoMatriculaPedido.Status.REJEITADO)

    actions = [
        {
            "label": "Voltar",
            "url": reverse("educacao:renovacao_matricula_list"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }
    ]

    return render(
        request,
        "educacao/renovacao_matricula_detail.html",
        {
            "renovacao": renovacao,
            "actions": actions,
            "oferta_form": oferta_form,
            "ofertas": ofertas,
            "pedidos": pedidos,
            "etapa_codigo": etapa_codigo,
            "etapa_label": etapa_label,
            "etapa_badge": _status_badge_class(etapa_codigo),
            "pendentes": pendentes,
            "aprovados": aprovados,
            "rejeitados": rejeitados,
            "can_processar": etapa_codigo in {
                RenovacaoMatricula.Etapa.AGUARDANDO_PROCESSAMENTO,
                RenovacaoMatricula.Etapa.AGUARDANDO_MATRICULA,
            }
            and pendentes > 0,
        },
    )
