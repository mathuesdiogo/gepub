from __future__ import annotations

from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.urls import reverse
from django.shortcuts import render
from django.utils import timezone

from apps.core.exports import export_csv, export_pdf_table
from apps.core.rbac import scope_filter_alunos, scope_filter_matriculas
from apps.educacao.models import Aluno, Matricula

from .models import AlunoNecessidade, TipoNecessidade


def _get_municipio_from_unidade(unidade):
    # tenta cadeias comuns sem quebrar
    if not unidade:
        return None
    for chain in [
        ("municipio",),
        ("secretaria", "municipio"),
        ("secretaria", "municipio", "nome"),
        ("municipio", "nome"),
        ("secretaria", "municipio", "nome"),
    ]:
        try:
            obj = unidade
            for attr in chain:
                obj = getattr(obj, attr)
            # se terminou em objeto com nome
            if hasattr(obj, "nome"):
                return obj.nome
            if isinstance(obj, str):
                return obj
        except Exception:
            continue
    # fallback: tenta propriedade
    return getattr(unidade, "municipio_nome", None)


@login_required
def relatorios_index(request):
    actions = [{"label": "Voltar", "url": reverse("nee:index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    cards = [
        {"title": "Por tipo", "description": "Distribuição de alunos por tipo de necessidade.", "icon": "fa-solid fa-tags", "url": reverse("nee:relatorios_por_tipo")},
        {"title": "Por município", "description": "Distribuição por município (com base nas unidades/turmas).", "icon": "fa-solid fa-city", "url": reverse("nee:relatorios_por_municipio")},
        {"title": "Por unidade", "description": "Distribuição por unidade escolar.", "icon": "fa-solid fa-school", "url": reverse("nee:relatorios_por_unidade")},
    ]
    return render(request, "nee/relatorios/index_enterprise.html", {"actions": actions, "cards": cards})


@login_required
def relatorios_por_tipo(request):
    alunos_qs = scope_filter_alunos(request.user, Aluno.objects.all())

    qs = (
        AlunoNecessidade.objects.filter(aluno__in=alunos_qs, ativo=True)
        .values("tipo_id", "tipo__nome")
        .annotate(total=Count("aluno_id", distinct=True))
        .order_by("-total", "tipo__nome")
    )

    items = []
    for r in qs:
        items.append(
            {
                "label": r["tipo__nome"],
                "total": r["total"],
                "url": reverse("nee:relatorios_alunos") + f"?tipo={r['tipo_id']}",
            }
        )

    # export
    if request.GET.get("export") in ("csv","pdf"):
        headers = ["Tipo", "Alunos"]
        rows = [[i["label"], i["total"]] for i in items]
        if request.GET.get("export") == "csv":
            return export_csv("nee_relatorio_por_tipo.csv", headers, rows)
        return export_pdf_table(request, filename="nee_relatorio_por_tipo.pdf", title="NEE — Relatório por tipo", headers=headers, rows=rows, subtitle="Alunos por tipo", filtros="")

    actions = [
        {"label": "Voltar", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Exportar CSV", "url": reverse("nee:relatorios_por_tipo") + "?export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "Exportar PDF", "url": reverse("nee:relatorios_por_tipo") + "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]
    return render(request, "nee/relatorios/por_tipo_enterprise.html", {"actions": actions, "items": items})


@login_required
def relatorios_por_unidade(request):
    alunos_qs = scope_filter_alunos(request.user, Aluno.objects.all())
    matriculas = scope_filter_matriculas(request.user, Matricula.objects.select_related("turma", "turma__unidade").filter(aluno__in=alunos_qs))

    # alunos com necessidades ativas
    alunos_com_nee = set(AlunoNecessidade.objects.filter(aluno__in=alunos_qs, ativo=True).values_list("aluno_id", flat=True).distinct())

    counter = defaultdict(set)  # unidade_id -> set(aluno_id)
    unidades = {}
    for m in matriculas:
        if m.aluno_id not in alunos_com_nee:
            continue
        unidade = getattr(m.turma, "unidade", None)
        if not unidade:
            continue
        counter[unidade.id].add(m.aluno_id)
        unidades[unidade.id] = unidade

    items = []
    for unidade_id, aluno_ids in counter.items():
        unidade = unidades[unidade_id]
        label = getattr(unidade, "nome", f"Unidade #{unidade_id}")
        items.append(
            {
                "label": label,
                "total": len(aluno_ids),
                "url": reverse("nee:relatorios_alunos") + f"?unidade={unidade_id}",
            }
        )
    items.sort(key=lambda x: (-x["total"], x["label"]))

    if request.GET.get("export") in ("csv","pdf"):
        headers = ["Unidade", "Alunos"]
        rows = [[i["label"], i["total"]] for i in items]
        if request.GET.get("export") == "csv":
            return export_csv("nee_relatorio_por_unidade.csv", headers, rows)
        return export_pdf_table(request, filename="nee_relatorio_por_unidade.pdf", title="NEE — Relatório por unidade", headers=headers, rows=rows, subtitle="Alunos por unidade", filtros="")

    actions = [
        {"label": "Voltar", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Exportar CSV", "url": reverse("nee:relatorios_por_unidade") + "?export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "Exportar PDF", "url": reverse("nee:relatorios_por_unidade") + "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]
    return render(request, "nee/relatorios/por_unidade_enterprise.html", {"actions": actions, "items": items})


@login_required
def relatorios_por_municipio(request):
    alunos_qs = scope_filter_alunos(request.user, Aluno.objects.all())
    matriculas = scope_filter_matriculas(request.user, Matricula.objects.select_related("turma", "turma__unidade").filter(aluno__in=alunos_qs))

    alunos_com_nee = set(AlunoNecessidade.objects.filter(aluno__in=alunos_qs, ativo=True).values_list("aluno_id", flat=True).distinct())

    counter = defaultdict(set)  # municipio_nome -> set(aluno_id)
    for m in matriculas:
        if m.aluno_id not in alunos_com_nee:
            continue
        unidade = getattr(m.turma, "unidade", None)
        mun = _get_municipio_from_unidade(unidade) or "—"
        counter[mun].add(m.aluno_id)

    items = []
    for mun, aluno_ids in counter.items():
        items.append(
            {
                "label": mun,
                "total": len(aluno_ids),
                "url": reverse("nee:relatorios_alunos") + f"?municipio={mun}",
            }
        )
    items.sort(key=lambda x: (-x["total"], x["label"]))

    if request.GET.get("export") in ("csv","pdf"):
        headers = ["Município", "Alunos"]
        rows = [[i["label"], i["total"]] for i in items]
        if request.GET.get("export") == "csv":
            return export_csv("nee_relatorio_por_municipio.csv", headers, rows)
        return export_pdf_table(request, filename="nee_relatorio_por_municipio.pdf", title="NEE — Relatório por município", headers=headers, rows=rows, subtitle="Alunos por município", filtros="")

    actions = [
        {"label": "Voltar", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Exportar CSV", "url": reverse("nee:relatorios_por_municipio") + "?export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "Exportar PDF", "url": reverse("nee:relatorios_por_municipio") + "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]
    return render(request, "nee/relatorios/por_municipio_enterprise.html", {"actions": actions, "items": items})


@login_required
def relatorios_alunos(request):
    alunos_qs = scope_filter_alunos(request.user, Aluno.objects.all())

    tipo_id = request.GET.get("tipo")
    unidade_id = request.GET.get("unidade")
    municipio = (request.GET.get("municipio") or "").strip()

    if tipo_id:
        alunos_qs = alunos_qs.filter(necessidades__tipo_id=tipo_id, necessidades__ativo=True).distinct()

    if unidade_id or municipio:
        matriculas = scope_filter_matriculas(request.user, Matricula.objects.select_related("turma", "turma__unidade").filter(aluno__in=alunos_qs))
        alvo_ids=set()
        for m in matriculas:
            unidade = getattr(m.turma, "unidade", None)
            if unidade_id and str(getattr(unidade,"id", "")) != str(unidade_id):
                continue
            if municipio and (_get_municipio_from_unidade(unidade) or "—") != municipio:
                continue
            alvo_ids.add(m.aluno_id)
        alunos_qs = alunos_qs.filter(id__in=alvo_ids)

    alunos = alunos_qs.order_by("nome")[:1000]

    headers = [
        {"label": "Aluno"},
        {"label": "CPF", "width": "160px"},
        {"label": "NIS", "width": "160px"},
    ]
    rows=[]
    for a in alunos:
        rows.append({
            "cells": [
                {"text": a.nome, "url": reverse("educacao:aluno_detail", args=[a.pk])},
                {"text": a.cpf or "—"},
                {"text": a.nis or "—"},
            ],
            "can_edit": False,
        })

    # export
    if request.GET.get("export") in ("csv","pdf"):
        head = ["Aluno", "CPF", "NIS"]
        rws = [[a.nome, a.cpf or "", a.nis or ""] for a in alunos]
        if request.GET.get("export") == "csv":
            return export_csv("nee_relatorio_alunos.csv", head, rws)
        return export_pdf_table(request, filename="nee_relatorio_alunos.pdf", title="NEE — Alunos", headers=head, rows=rws, subtitle="Lista de alunos", filtros="")

    actions = [
        {"label": "Voltar", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Exportar CSV", "url": request.get_full_path() + ("&" if "?" in request.get_full_path() else "?") + "export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "Exportar PDF", "url": request.get_full_path() + ("&" if "?" in request.get_full_path() else "?") + "export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]
    # título de contexto
    filtro_txt = ""
    if tipo_id:
        t = TipoNecessidade.objects.filter(id=tipo_id).first()
        filtro_txt = f"Tipo: {t.nome if t else tipo_id}"
    if unidade_id:
        filtro_txt = (filtro_txt + " • " if filtro_txt else "") + f"Unidade: {unidade_id}"
    if municipio:
        filtro_txt = (filtro_txt + " • " if filtro_txt else "") + f"Município: {municipio}"

    return render(request, "nee/relatorios/alunos_list.html", {"actions": actions, "headers": headers, "rows": rows, "filtro_txt": filtro_txt})
