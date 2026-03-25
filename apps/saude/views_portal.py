from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import scope_filter_unidades
from apps.educacao.models_beneficios import BeneficioEdital, BeneficioEditalInscricao, BeneficioTipo
from apps.org.models import Unidade

from .models import PacienteSaude


def _scoped_unidades_saude(user):
    return scope_filter_unidades(user, Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE, ativo=True))


def _scoped_pacientes(user):
    unidades_qs = _scoped_unidades_saude(user)
    return PacienteSaude.objects.select_related("unidade_referencia", "aluno").filter(
        unidade_referencia_id__in=unidades_qs.values_list("id", flat=True)
    )


def _timeline_etapas(edital: BeneficioEdital):
    status_ord = {
        BeneficioEdital.Status.RASCUNHO: 1,
        BeneficioEdital.Status.PUBLICADO: 2,
        BeneficioEdital.Status.INSCRICOES_ENCERRADAS: 3,
        BeneficioEdital.Status.EM_ANALISE: 4,
        BeneficioEdital.Status.RESULTADO_PRELIMINAR: 5,
        BeneficioEdital.Status.EM_RECURSOS: 6,
        BeneficioEdital.Status.RESULTADO_FINAL: 7,
        BeneficioEdital.Status.ENCERRADO: 8,
    }
    current = status_ord.get(edital.status, 1)
    etapas = [
        ("Publicado", edital.inscricao_inicio, 2),
        ("Inscrições encerradas", edital.inscricao_fim, 3),
        ("Análise", edital.analise_fim, 4),
        ("Resultado preliminar", edital.resultado_preliminar_data, 5),
        ("Prazo de recurso", edital.prazo_recurso_data, 6),
        ("Resultado final", edital.resultado_final_data, 7),
        ("Encerrado", None, 8),
    ]
    return [
        {
            "nome": nome,
            "data": data_ref,
            "concluida": current >= ord_idx,
            "atual": current == ord_idx,
        }
        for nome, data_ref, ord_idx in etapas
    ]


@login_required
@require_perm("saude.view")
def portal_inscritos_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()

    pacientes_qs = _scoped_pacientes(request.user)
    aluno_ids = list(pacientes_qs.exclude(aluno_id__isnull=True).values_list("aluno_id", flat=True))

    inscricoes_qs = (
        BeneficioEditalInscricao.objects.select_related("edital", "edital__beneficio", "aluno", "escola", "turma")
        .filter(edital__area=BeneficioTipo.Area.SAUDE, aluno_id__in=aluno_ids)
        .order_by("-data_hora", "-id")
    )
    if q:
        inscricoes_qs = inscricoes_qs.filter(
            Q(aluno__nome__icontains=q)
            | Q(edital__titulo__icontains=q)
            | Q(edital__numero_ano__icontains=q)
            | Q(edital__beneficio__nome__icontains=q)
        )
    if status:
        inscricoes_qs = inscricoes_qs.filter(status=status)

    page_obj = Paginator(inscricoes_qs, 20).get_page(request.GET.get("page"))

    aluno_to_paciente = {
        p.aluno_id: p
        for p in pacientes_qs.filter(aluno_id__in=[i.aluno_id for i in page_obj]).select_related("aluno")
    }

    rows = []
    for i in page_obj:
        paciente = aluno_to_paciente.get(i.aluno_id)
        paciente_link = reverse("saude:portal_paciente_inscricoes", args=[paciente.pk]) if paciente else ""
        inscricao_link = reverse("saude:portal_paciente_inscricao_detail", args=[paciente.pk, i.pk]) if paciente else ""
        rows.append(
            {
                "cells": [
                    {"text": i.aluno.nome, "url": paciente_link},
                    {"text": i.edital.numero_ano},
                    {"text": i.edital.titulo, "url": inscricao_link},
                    {"text": i.get_status_display()},
                    {"text": str(i.pontuacao)},
                    {"text": i.edital.get_status_display()},
                    {"text": i.data_hora.strftime("%d/%m/%Y %H:%M")},
                ]
            }
        )

    actions = [
        {
            "label": "Pacientes",
            "url": reverse("saude:paciente_list"),
            "icon": "fa-solid fa-user-injured",
            "variant": "gp-button--ghost",
        }
    ]

    return render(
        request,
        "saude/portal_inscritos_list.html",
        {
            "title": "Portal de Inscritos (Saúde)",
            "subtitle": "Acompanhamento de etapas e andamento dos editais da Saúde",
            "q": q,
            "status": status,
            "status_choices": BeneficioEditalInscricao.Status.choices,
            "page_obj": page_obj,
            "headers": [
                {"label": "Paciente"},
                {"label": "Edital", "width": "130px"},
                {"label": "Título"},
                {"label": "Status inscrição", "width": "150px"},
                {"label": "Pontuação", "width": "100px"},
                {"label": "Andamento edital", "width": "150px"},
                {"label": "Data", "width": "130px"},
            ],
            "rows": rows,
            "actions": actions,
            "action_url": reverse("saude:portal_inscritos_list"),
            "clear_url": reverse("saude:portal_inscritos_list"),
            "has_filters": bool(q or status),
            "empty_title": "Sem inscrições em editais da Saúde",
            "empty_text": "Ainda não existem inscrições para os pacientes do seu escopo.",
        },
    )


@login_required
@require_perm("saude.view")
def portal_paciente_inscricoes(request, pk: int):
    paciente = get_object_or_404(_scoped_pacientes(request.user), pk=pk)
    inscricoes = BeneficioEditalInscricao.objects.none()
    if paciente.aluno_id:
        inscricoes = (
            BeneficioEditalInscricao.objects.select_related("edital", "edital__beneficio", "escola", "turma")
            .filter(edital__area=BeneficioTipo.Area.SAUDE, aluno_id=paciente.aluno_id)
            .order_by("-data_hora", "-id")
        )

    rows = []
    for i in inscricoes:
        rows.append(
            {
                "cells": [
                    {"text": i.edital.numero_ano},
                    {"text": i.edital.titulo, "url": reverse("saude:portal_paciente_inscricao_detail", args=[paciente.pk, i.pk])},
                    {"text": i.edital.beneficio.nome},
                    {"text": i.get_status_display()},
                    {"text": str(i.pontuacao)},
                    {"text": i.edital.get_status_display()},
                    {"text": i.data_hora.strftime("%d/%m/%Y %H:%M")},
                ]
            }
        )

    actions = [
        {
            "label": "Voltar ao paciente",
            "url": reverse("saude:paciente_detail", args=[paciente.pk]),
            "icon": "fa-solid fa-arrow-left",
            "variant": "gp-button--ghost",
        }
    ]

    return render(
        request,
        "saude/portal_paciente_inscricoes.html",
        {
            "paciente": paciente,
            "inscricoes": inscricoes,
            "actions": actions,
            "headers": [
                {"label": "Edital", "width": "130px"},
                {"label": "Título"},
                {"label": "Benefício"},
                {"label": "Status inscrição", "width": "140px"},
                {"label": "Pontuação", "width": "90px"},
                {"label": "Andamento edital", "width": "150px"},
                {"label": "Data", "width": "130px"},
            ],
            "rows": rows,
        },
    )


@login_required
@require_perm("saude.view")
def portal_paciente_inscricao_detail(request, pk: int, inscricao_id: int):
    paciente = get_object_or_404(_scoped_pacientes(request.user), pk=pk)
    if not paciente.aluno_id:
        return render(
            request,
            "saude/portal_paciente_inscricao_detail.html",
            {
                "paciente": paciente,
                "inscricao": None,
                "actions": [
                    {
                        "label": "Voltar",
                        "url": reverse("saude:portal_paciente_inscricoes", args=[paciente.pk]),
                        "icon": "fa-solid fa-arrow-left",
                        "variant": "gp-button--ghost",
                    }
                ],
                "timeline_etapas": [],
                "avaliacao": {},
                "pendencias_documentos": [],
            },
        )

    inscricao = get_object_or_404(
        BeneficioEditalInscricao.objects.select_related("edital", "edital__beneficio", "escola", "turma").prefetch_related("documentos", "recursos"),
        pk=inscricao_id,
        aluno_id=paciente.aluno_id,
        edital__area=BeneficioTipo.Area.SAUDE,
    )
    dados_json = inscricao.dados_json or {}
    avaliacao = dados_json.get("avaliacao") or {}
    pendencias = avaliacao.get("pendencias_documentos") or []

    return render(
        request,
        "saude/portal_paciente_inscricao_detail.html",
        {
            "paciente": paciente,
            "inscricao": inscricao,
            "edital": inscricao.edital,
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("saude:portal_paciente_inscricoes", args=[paciente.pk]),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                }
            ],
            "timeline_etapas": _timeline_etapas(inscricao.edital),
            "avaliacao": avaliacao,
            "pendencias_documentos": pendencias,
        },
    )
