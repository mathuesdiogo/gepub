from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from apps.core.exports import export_csv, export_pdf_table
from apps.educacao.models import Aluno, Matricula
from .models import TipoNecessidade, AlunoNecessidade


def _aluno_actions_html(aluno_id: int) -> str:
    # HTML seguro: o core/table_shell já suporta cell.html|safe
    return (
        f'<a class="btn btn--ghost btn--sm" href="/nee/alunos/{aluno_id}/necessidades/"><i class="fa-solid fa-tags"></i> Necessidades</a> '
        f'<a class="btn btn--ghost btn--sm" href="/nee/alunos/{aluno_id}/laudos/"><i class="fa-solid fa-file-medical"></i> Laudos</a> '
        f'<a class="btn btn--ghost btn--sm" href="/nee/alunos/{aluno_id}/recursos/"><i class="fa-solid fa-screwdriver-wrench"></i> Recursos</a> '
        f'<a class="btn btn--ghost btn--sm" href="/nee/alunos/{aluno_id}/timeline/"><i class="fa-solid fa-timeline"></i> Timeline</a>'
    )


def _alunos_rows(alunos_qs):
    rows = []
    for a in alunos_qs:
        rows.append({
            "cells": [
                {"text": getattr(a, "nome", str(a)), "url": reverse("educacao:aluno_detail", args=[a.pk])},
                {"text": getattr(a, "cpf", "") or "—", "width": "160px"},
                {"text": getattr(a, "nis", "") or "—", "width": "160px"},
                {"text": "Sim" if getattr(a, "ativo", True) else "Não", "width": "120px"},
                {"html": _aluno_actions_html(a.pk), "width": "520px"},
            ]
        })
    return rows


@login_required
def relatorio_por_tipo(request):
    qs = (
        AlunoNecessidade.objects
        .select_related("tipo")
        .values("tipo_id", "tipo__nome")
        .annotate(qtd=Count("aluno", distinct=True))
        .order_by("-qtd", "tipo__nome")
    )
    rows = [{
        "tipo_id": x["tipo_id"],
        "tipo": x["tipo__nome"],
        "qtd": x["qtd"],
        "url": reverse("nee:relatorios_alunos") + f"?tipo={x['tipo_id']}",
    } for x in qs]

    # Export padrão GEPUB (CSV/PDF)
    if request.GET.get("export") == "csv":
        return export_csv(
            "nee_relatorio_por_tipo.csv",
            ["Tipo", "Alunos"],
            [[r["tipo"], str(r["qtd"])] for r in rows],
        )
    if request.GET.get("export") == "pdf":
        return export_pdf_table(
            request,
            filename="nee_relatorio_por_tipo.pdf",
            title="NEE — Relatório por tipo",
            subtitle="Clique em um tipo para drilldown (lista de alunos)",
            headers=["Tipo", "Alunos"],
            rows=[[r["tipo"], str(r["qtd"])] for r in rows],
        )

    actions = [
        {"label": "Exportar CSV", "url": "?export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "Exportar PDF", "url": "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
        {"label": "Voltar", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
    ]
    return render(request, "nee/relatorios/por_tipo_enterprise.html", {"actions": actions, "rows": rows})


@login_required
def relatorio_tipo_alunos(request, tipo_id: int):
    tipo = get_object_or_404(TipoNecessidade, pk=tipo_id)
    aluno_ids = (
        AlunoNecessidade.objects
        .filter(tipo_id=tipo_id)
        .values_list("aluno_id", flat=True)
        .distinct()
    )
    alunos = Aluno.objects.filter(id__in=aluno_ids).order_by("nome")

    if request.GET.get("export") == "csv":
        return export_csv(
            "nee_alunos_por_tipo.csv",
            ["Aluno", "CPF", "NIS", "Ativo"],
            [[getattr(a, "nome", str(a)), getattr(a, "cpf", "") or "", getattr(a, "nis", "") or "", "Sim" if getattr(a, "ativo", True) else "Não"] for a in alunos],
        )
    if request.GET.get("export") == "pdf":
        return export_pdf_table(
            request,
            filename="nee_alunos_por_tipo.pdf",
            title="NEE — Alunos por tipo",
            subtitle=f"{tipo.nome} • {alunos.count()} alunos",
            headers=["Aluno", "CPF", "NIS", "Ativo"],
            rows=[[getattr(a, "nome", str(a)), getattr(a, "cpf", "") or "—", getattr(a, "nis", "") or "—", "Sim" if getattr(a, "ativo", True) else "Não"] for a in alunos],
        )

    headers = [
        {"label": "Aluno"},
        {"label": "CPF", "width": "160px"},
        {"label": "NIS", "width": "160px"},
        {"label": "Ativo", "width": "120px"},
        {"label": "Ações"},
    ]
    ctx = {
        "actions": [
            {"label": "Voltar", "url": reverse("nee:relatorios_por_tipo"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Exportar CSV", "url": "?export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
            {"label": "Exportar PDF", "url": "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
        ],
        "title": "Alunos por tipo",
        "subtitle": f"{tipo.nome} • {alunos.count()} alunos",
        "headers": headers,
        "rows": _alunos_rows(alunos),
        "empty_title": "Sem alunos",
        "empty_text": "Nenhum aluno encontrado para este tipo.",
        "page_obj": None,
        "q": "",
    }
    return render(request, "nee/relatorios/alunos_list.html", ctx)


@login_required
def relatorio_por_municipio(request):
    qs = (
        Matricula.objects
        .select_related("turma__unidade__secretaria__municipio")
        .filter(aluno__necessidades_nee__isnull=False)
        .values("turma__unidade__secretaria__municipio__id", "turma__unidade__secretaria__municipio__nome")
        .annotate(qtd=Count("aluno", distinct=True))
        .order_by("-qtd", "turma__unidade__secretaria__municipio__nome")
    )
    rows = [{
        "municipio_id": x["turma__unidade__secretaria__municipio__id"],
        "municipio": x["turma__unidade__secretaria__municipio__nome"] or "—",
        "qtd": x["qtd"],
        "url": reverse("nee:relatorios_alunos") + f"?municipio={x['turma__unidade__secretaria__municipio__nome']}",
    } for x in qs]

    if request.GET.get("export") == "csv":
        return export_csv("nee_relatorio_por_municipio.csv", ["Município", "Alunos"], [[r["municipio"], str(r["qtd"])] for r in rows])
    if request.GET.get("export") == "pdf":
        return export_pdf_table(
            request,
            filename="nee_relatorio_por_municipio.pdf",
            title="NEE — Relatório por município",
            headers=["Município", "Alunos"],
            rows=[[r["municipio"], str(r["qtd"])] for r in rows],
        )

    actions = [
        {"label": "Exportar CSV", "url": "?export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "Exportar PDF", "url": "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
        {"label": "Voltar", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
    ]
    return render(request, "nee/relatorios/por_municipio_enterprise.html", {"actions": actions, "rows": rows})


@login_required
def relatorio_municipio_alunos(request, municipio_id: int):
    aluno_ids = (
        Matricula.objects
        .filter(turma__unidade__secretaria__municipio__id=municipio_id, aluno__necessidades_nee__isnull=False)
        .values_list("aluno_id", flat=True)
        .distinct()
    )
    alunos = Aluno.objects.filter(id__in=aluno_ids).order_by("nome")

    if request.GET.get("export") == "csv":
        return export_csv(
            "nee_alunos_por_municipio.csv",
            ["Aluno", "CPF", "NIS", "Ativo"],
            [[getattr(a, "nome", str(a)), getattr(a, "cpf", "") or "", getattr(a, "nis", "") or "", "Sim" if getattr(a, "ativo", True) else "Não"] for a in alunos],
        )
    if request.GET.get("export") == "pdf":
        return export_pdf_table(
            request,
            filename="nee_alunos_por_municipio.pdf",
            title="NEE — Alunos por município",
            subtitle=f"{alunos.count()} alunos com NEE",
            headers=["Aluno", "CPF", "NIS", "Ativo"],
            rows=[[getattr(a, "nome", str(a)), getattr(a, "cpf", "") or "—", getattr(a, "nis", "") or "—", "Sim" if getattr(a, "ativo", True) else "Não"] for a in alunos],
        )

    headers = [
        {"label": "Aluno"},
        {"label": "CPF", "width": "160px"},
        {"label": "NIS", "width": "160px"},
        {"label": "Ativo", "width": "120px"},
        {"label": "Ações"},
    ]
    ctx = {
        "actions": [
            {"label": "Voltar", "url": reverse("nee:relatorios_por_municipio"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Exportar CSV", "url": "?export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
            {"label": "Exportar PDF", "url": "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
        ],
        "title": "Alunos por município",
        "subtitle": f"{alunos.count()} alunos com NEE",
        "headers": headers,
        "rows": _alunos_rows(alunos),
        "empty_title": "Sem alunos",
        "empty_text": "Nenhum aluno encontrado para este município.",
        "page_obj": None,
        "q": "",
    }
    return render(request, "nee/relatorios/alunos_list.html", ctx)


@login_required
def relatorio_por_unidade(request):
    qs = (
        Matricula.objects
        .select_related("turma__unidade__secretaria__municipio")
        .filter(aluno__necessidades_nee__isnull=False)
        .values("turma__unidade__id", "turma__unidade__nome", "turma__unidade__secretaria__municipio__nome")
        .annotate(qtd=Count("aluno", distinct=True))
        .order_by("-qtd", "turma__unidade__secretaria__municipio__nome", "turma__unidade__nome")
    )
    rows = [{
        "unidade_id": x["turma__unidade__id"],
        "municipio": x["turma__unidade__secretaria__municipio__nome"] or "—",
        "unidade": x["turma__unidade__nome"] or "—",
        "qtd": x["qtd"],
        "url": reverse("nee:relatorios_alunos") + f"?unidade={x['turma__unidade__id']}",
    } for x in qs]

    if request.GET.get("export") == "csv":
        return export_csv("nee_relatorio_por_unidade.csv", ["Município", "Unidade", "Alunos"], [[r["municipio"], r["unidade"], str(r["qtd"])] for r in rows])
    if request.GET.get("export") == "pdf":
        return export_pdf_table(
            request,
            filename="nee_relatorio_por_unidade.pdf",
            title="NEE — Relatório por unidade",
            headers=["Município", "Unidade", "Alunos"],
            rows=[[r["municipio"], r["unidade"], str(r["qtd"])] for r in rows],
        )

    actions = [
        {"label": "Exportar CSV", "url": "?export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "Exportar PDF", "url": "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
        {"label": "Voltar", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
    ]
    return render(request, "nee/relatorios/por_unidade_enterprise.html", {"actions": actions, "rows": rows})


@login_required
def relatorio_unidade_alunos(request, unidade_id: int):
    aluno_ids = (
        Matricula.objects
        .filter(turma__unidade__id=unidade_id, aluno__necessidades_nee__isnull=False)
        .values_list("aluno_id", flat=True)
        .distinct()
    )
    alunos = Aluno.objects.filter(id__in=aluno_ids).order_by("nome")

    if request.GET.get("export") == "csv":
        return export_csv(
            "nee_alunos_por_unidade.csv",
            ["Aluno", "CPF", "NIS", "Ativo"],
            [[getattr(a, "nome", str(a)), getattr(a, "cpf", "") or "", getattr(a, "nis", "") or "", "Sim" if getattr(a, "ativo", True) else "Não"] for a in alunos],
        )
    if request.GET.get("export") == "pdf":
        return export_pdf_table(
            request,
            filename="nee_alunos_por_unidade.pdf",
            title="NEE — Alunos por unidade",
            subtitle=f"{alunos.count()} alunos com NEE",
            headers=["Aluno", "CPF", "NIS", "Ativo"],
            rows=[[getattr(a, "nome", str(a)), getattr(a, "cpf", "") or "—", getattr(a, "nis", "") or "—", "Sim" if getattr(a, "ativo", True) else "Não"] for a in alunos],
        )

    headers = [
        {"label": "Aluno"},
        {"label": "CPF", "width": "160px"},
        {"label": "NIS", "width": "160px"},
        {"label": "Ativo", "width": "120px"},
        {"label": "Ações"},
    ]
    ctx = {
        "actions": [
            {"label": "Voltar", "url": reverse("nee:relatorios_por_unidade"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Exportar CSV", "url": "?export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
            {"label": "Exportar PDF", "url": "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
        ],
        "title": "Alunos por unidade",
        "subtitle": f"{alunos.count()} alunos com NEE",
        "headers": headers,
        "rows": _alunos_rows(alunos),
        "empty_title": "Sem alunos",
        "empty_text": "Nenhum aluno encontrado para esta unidade.",
        "page_obj": None,
        "q": "",
    }
    return render(request, "nee/relatorios/alunos_list.html", ctx)
