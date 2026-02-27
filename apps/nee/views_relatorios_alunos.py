from __future__ import annotations

from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from django.urls import reverse

from apps.core.exports import export_csv, export_pdf_table
from apps.core.rbac import scope_filter_alunos, scope_filter_matriculas
from apps.educacao.models import Aluno, Matricula

from .models import AlunoNecessidade, TipoNecessidade
from .views_relatorios_common import get_municipio_from_unidade


@login_required
def relatorios_alunos(request):
    alunos_qs = scope_filter_alunos(request.user, Aluno.objects.all())

    tipo_id = request.GET.get("tipo")
    unidade_id = request.GET.get("unidade")
    municipio = (request.GET.get("municipio") or "").strip()

    if tipo_id:
        alunos_qs = alunos_qs.filter(necessidades__tipo_id=tipo_id, necessidades__ativo=True).distinct()

    matriculas_all = scope_filter_matriculas(
        request.user,
        Matricula.objects.select_related("turma", "turma__unidade").filter(aluno__in=alunos_qs),
    )

    if unidade_id or municipio:
        alvo_ids = set()
        for m in matriculas_all:
            unidade = getattr(m.turma, "unidade", None)
            if unidade_id and str(getattr(unidade, "id", "")) != str(unidade_id):
                continue
            if municipio and (get_municipio_from_unidade(unidade) or "—") != municipio:
                continue
            alvo_ids.add(m.aluno_id)
        alunos_qs = alunos_qs.filter(id__in=alvo_ids)

    alunos_qs = alunos_qs.order_by("nome")

    paginator = Paginator(alunos_qs, 10)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)
    alunos = list(page_obj.object_list)

    aluno_ids = [a.id for a in alunos]

    matriculas_page = [m for m in matriculas_all if m.aluno_id in set(aluno_ids)]

    info_by_aluno = {}
    for m in matriculas_page:
        if m.aluno_id in info_by_aluno:
            continue
        unidade = getattr(m.turma, "unidade", None)
        info_by_aluno[m.aluno_id] = {
            "municipio": get_municipio_from_unidade(unidade) or "—",
            "unidade": getattr(unidade, "nome", "—") if unidade else "—",
            "turma": getattr(m.turma, "nome", "—") if m.turma else "—",
        }

    nec_page = (
        AlunoNecessidade.objects.filter(aluno_id__in=aluno_ids, ativo=True)
        .select_related("tipo")
        .order_by("tipo__nome")
    )
    tipos_by_aluno = defaultdict(list)
    cids_by_aluno = defaultdict(list)
    qtd_by_aluno = defaultdict(int)

    for n in nec_page:
        qtd_by_aluno[n.aluno_id] += 1
        nome_tipo = getattr(n.tipo, "nome", "—")
        if nome_tipo and nome_tipo not in tipos_by_aluno[n.aluno_id]:
            tipos_by_aluno[n.aluno_id].append(nome_tipo)
        if n.cid:
            if n.cid not in cids_by_aluno[n.aluno_id]:
                cids_by_aluno[n.aluno_id].append(n.cid)

    headers = [
        {"label": "Aluno"},
        {"label": "CPF"},
        {"label": "NIS"},
        {"label": "Município"},
        {"label": "Unidade"},
        {"label": "Turma"},
        {"label": "Tipos NEE"},
        {"label": "CIDs"},
        {"label": "Qtde"},
    ]

    rows = []
    for a in alunos:
        info = info_by_aluno.get(a.id, {"municipio": "—", "unidade": "—", "turma": "—"})
        tipos_txt = ", ".join(tipos_by_aluno.get(a.id, [])) or "—"
        cids_txt = ", ".join(cids_by_aluno.get(a.id, [])) or "—"
        qtd = qtd_by_aluno.get(a.id, 0)

        rows.append(
            {
                "cells": [
                    {"text": a.nome, "url": reverse("educacao:aluno_detail", args=[a.pk])},
                    {"text": a.cpf or "—"},
                    {"text": a.nis or "—"},
                    {"text": info["municipio"]},
                    {"text": info["unidade"]},
                    {"text": info["turma"]},
                    {"text": tipos_txt},
                    {"text": cids_txt},
                    {"text": str(qtd)},
                ],
                "can_edit": False,
            }
        )

    if request.GET.get("export") in ("csv", "pdf"):
        all_ids = list(alunos_qs.values_list("id", flat=True)[:5000])
        all_alunos = list(Aluno.objects.filter(id__in=all_ids).order_by("nome"))

        mats_export = scope_filter_matriculas(
            request.user,
            Matricula.objects.select_related("turma", "turma__unidade").filter(aluno_id__in=all_ids),
        )
        info_export = {}
        for m in mats_export:
            if m.aluno_id in info_export:
                continue
            unidade = getattr(m.turma, "unidade", None)
            info_export[m.aluno_id] = {
                "municipio": get_municipio_from_unidade(unidade) or "—",
                "unidade": getattr(unidade, "nome", "—") if unidade else "—",
                "turma": getattr(m.turma, "nome", "—") if m.turma else "—",
            }

        nec_export = (
            AlunoNecessidade.objects.filter(aluno_id__in=all_ids, ativo=True)
            .select_related("tipo")
            .order_by("tipo__nome")
        )
        tipos_export = defaultdict(list)
        cids_export = defaultdict(list)
        qtd_export = defaultdict(int)
        for n in nec_export:
            qtd_export[n.aluno_id] += 1
            tnome = getattr(n.tipo, "nome", "—")
            if tnome and tnome not in tipos_export[n.aluno_id]:
                tipos_export[n.aluno_id].append(tnome)
            if n.cid and n.cid not in cids_export[n.aluno_id]:
                cids_export[n.aluno_id].append(n.cid)

        head = ["Aluno", "CPF", "NIS", "Município", "Unidade", "Turma", "Tipos NEE", "CIDs", "Qtde"]
        rws = []
        for a in all_alunos:
            inf = info_export.get(a.id, {"municipio": "—", "unidade": "—", "turma": "—"})
            rws.append(
                [
                    a.nome,
                    a.cpf or "",
                    a.nis or "",
                    inf["municipio"],
                    inf["unidade"],
                    inf["turma"],
                    ", ".join(tipos_export.get(a.id, [])) or "",
                    ", ".join(cids_export.get(a.id, [])) or "",
                    str(qtd_export.get(a.id, 0)),
                ]
            )

        if request.GET.get("export") == "csv":
            return export_csv("nee_relatorio_alunos.csv", head, rws)
        return export_pdf_table(
            request,
            filename="nee_relatorio_alunos.pdf",
            title="NEE — Relatório de alunos",
            headers=head,
            rows=rws,
            subtitle="Lista de alunos (com unidade/turma e necessidades ativas)",
            filtros="Somente necessidades ativas",
        )

    base_path = request.path
    qs_no_export = request.GET.copy()
    qs_no_export.pop("export", None)

    def _with_export(fmt: str) -> str:
        q = qs_no_export.copy()
        q["export"] = fmt
        return base_path + "?" + q.urlencode()

    actions = [
        {"label": "Voltar", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Exportar CSV", "url": _with_export("csv"), "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "Exportar PDF", "url": _with_export("pdf"), "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]

    filtro_txt = ""
    if tipo_id:
        t = TipoNecessidade.objects.filter(id=tipo_id).first()
        filtro_txt = f"Tipo: {t.nome if t else tipo_id}"
    if unidade_id:
        filtro_txt = (filtro_txt + " • " if filtro_txt else "") + f"Unidade: {unidade_id}"
    if municipio:
        filtro_txt = (filtro_txt + " • " if filtro_txt else "") + f"Município: {municipio}"

    title = "Relatório — Alunos"
    subtitle = filtro_txt or "Lista de alunos (paginado: 10 por página)."

    return render(
        request,
        "nee/relatorios/alunos_list.html",
        {
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "page_obj": page_obj,
            "q": request.GET.urlencode(),
            "title": title,
            "subtitle": subtitle,
            "empty_title": "Sem alunos",
            "empty_text": "Nenhum aluno encontrado para este filtro.",
        },
    )
