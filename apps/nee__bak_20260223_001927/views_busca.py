from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse

from apps.core.rbac import scope_filter_alunos, scope_filter_matriculas
from apps.educacao.models import Aluno, Matricula


def _alunos_nee_qs(user):
    # somente alunos com necessidade ativa (NEE)
    qs = scope_filter_alunos(user, Aluno.objects.all())
    return qs.filter(necessidades__ativo=True).distinct()


def _unidade_nome_from_matricula(m):
    turma = getattr(m, "turma", None)
    unidade = getattr(turma, "unidade", None) if turma else None
    return getattr(unidade, "nome", None) or "—"


@login_required
def buscar_aluno(request):
    q = (request.GET.get("q") or "").strip()
    page_number = request.GET.get("page") or 1

    alunos_qs = _alunos_nee_qs(request.user)

    if q:
        alunos_qs = alunos_qs.filter(nome__icontains=q)

    alunos_qs = alunos_qs.order_by("nome")

    paginator = Paginator(alunos_qs, 10)
    page_obj = paginator.get_page(page_number)

    # buscar matrículas apenas dos alunos da página para achar unidade
    aluno_ids = list(page_obj.object_list.values_list("id", flat=True))
    matriculas = scope_filter_matriculas(
        request.user,
        Matricula.objects.select_related("turma", "turma__unidade").filter(aluno_id__in=aluno_ids),
    )

    # pega a "última" matrícula por aluno (por id)
    mat_map = {}
    for m in matriculas:
        prev = mat_map.get(m.aluno_id)
        if (prev is None) or (m.id > prev.id):
            mat_map[m.aluno_id] = m

    headers = [
        {"label": "Aluno"},
        {"label": "CPF", "width": "150px"},
        {"label": "NIS", "width": "150px"},
        {"label": "Unidade"},
    ]

    rows = []
    for a in page_obj.object_list:
        m = mat_map.get(a.id)
        unidade_nome = _unidade_nome_from_matricula(m) if m else "—"

        rows.append(
            {
                "cells": [
                    {"text": a.nome, "url": reverse("nee:aluno_hub", args=[a.pk])},
                    {"text": getattr(a, "cpf", None) or "—"},
                    {"text": getattr(a, "nis", None) or "—"},
                    {"text": unidade_nome},
                ]
            }
        )

    actions = [
        {"label": "Voltar", "url": reverse("nee:index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
    ]

    return render(
        request,
        "nee/buscar_aluno.html",
        {
            "headers": headers,
            "rows": rows,
            "actions": actions,
            "q": q,
            "page_obj": page_obj,
        },
    )


@login_required
def buscar_aluno_autocomplete(request):
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    alunos_qs = _alunos_nee_qs(request.user).filter(nome__icontains=q).order_by("nome")[:10]

    results = []
    for a in alunos_qs:
        results.append(
            {
                "id": a.id,
                "label": a.nome,
                "url": reverse("nee:aluno_hub", args=[a.pk]),
            }
        )

    return JsonResponse({"results": results})