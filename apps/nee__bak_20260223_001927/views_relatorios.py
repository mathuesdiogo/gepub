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

    # necessidades ativas por tipo (alunos + necessidades)
    nec_qs = (
        AlunoNecessidade.objects.filter(aluno__in=alunos_qs, ativo=True)
        .select_related("tipo", "aluno")
    )

    # mapa aluno -> (unidade, municipio) pela matrícula (pra enriquecer o relatório)
    matriculas = scope_filter_matriculas(
        request.user,
        Matricula.objects.select_related("turma", "turma__unidade").filter(aluno__in=alunos_qs),
    )

    aluno_unidade = {}
    aluno_municipio = {}
    for m in matriculas:
        unidade = getattr(m.turma, "unidade", None)
        if not unidade:
            continue
        # guarda primeira ocorrência
        if m.aluno_id not in aluno_unidade:
            aluno_unidade[m.aluno_id] = getattr(unidade, "id", None)
        if m.aluno_id not in aluno_municipio:
            aluno_municipio[m.aluno_id] = _get_municipio_from_unidade(unidade) or "—"

    # agregação em python (mais estável pro seu modelo atual)
    by_tipo = {}  # tipo_id -> dict
    for n in nec_qs:
        tipo = n.tipo
        tipo_id = tipo.id
        if tipo_id not in by_tipo:
            by_tipo[tipo_id] = {
                "label": getattr(tipo, "nome", f"Tipo #{tipo_id}"),
                "alunos": set(),
                "nec": 0,
                "unidades": set(),
                "municipios": set(),
            }
        bucket = by_tipo[tipo_id]
        bucket["alunos"].add(n.aluno_id)
        bucket["nec"] += 1
        uid = aluno_unidade.get(n.aluno_id)
        if uid:
            bucket["unidades"].add(uid)
        bucket["municipios"].add(aluno_municipio.get(n.aluno_id, "—"))

    items = []
    for tipo_id, b in by_tipo.items():
        items.append(
            {
                "label": b["label"],
                "total_alunos": len(b["alunos"]),
                "total_nec": b["nec"],
                "total_unidades": len(b["unidades"]),
                "total_municipios": len(b["municipios"]),
                "url": reverse("nee:relatorios_alunos") + f"?tipo={tipo_id}",
            }
        )
    items.sort(key=lambda x: (-x["total_alunos"], x["label"]))

    if request.GET.get("export") in ("csv", "pdf"):
        headers = ["Tipo", "Alunos", "Necessidades (ativas)", "Unidades", "Municípios"]
        rows = [[i["label"], i["total_alunos"], i["total_nec"], i["total_unidades"], i["total_municipios"]] for i in items]
        if request.GET.get("export") == "csv":
            return export_csv("nee_relatorio_por_tipo.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="nee_relatorio_por_tipo.pdf",
            title="NEE — Relatório por tipo",
            headers=headers,
            rows=rows,
            subtitle="Alunos por tipo de necessidade",
            filtros="Somente necessidades ativas",
        )

    actions = [
        {"label": "Voltar", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Exportar CSV", "url": reverse("nee:relatorios_por_tipo") + "?export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "Exportar PDF", "url": reverse("nee:relatorios_por_tipo") + "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]
    return render(request, "nee/relatorios/por_tipo_enterprise.html", {"items": items, "actions": actions})


@login_required
def relatorios_por_unidade(request):
    alunos_qs = scope_filter_alunos(request.user, Aluno.objects.all())

    matriculas = scope_filter_matriculas(
        request.user,
        Matricula.objects.select_related("turma", "turma__unidade").filter(aluno__in=alunos_qs),
    )

    # necessidades ativas
    nec_qs = AlunoNecessidade.objects.filter(aluno__in=alunos_qs, ativo=True)

    alunos_com_nee = set(nec_qs.values_list("aluno_id", flat=True).distinct())

    # aluno -> qtd necessidades (ativas)
    nec_count_by_aluno = defaultdict(int)
    for row in nec_qs.values("aluno_id").annotate(c=Count("id")):
        nec_count_by_aluno[row["aluno_id"]] = row["c"]

    counter_alunos = defaultdict(set)   # unidade_id -> set(aluno_id)
    counter_turmas = defaultdict(set)   # unidade_id -> set(turma_id)
    counter_nec = defaultdict(int)      # unidade_id -> total necessidades ativas somadas
    unidades = {}

    for m in matriculas:
        if m.aluno_id not in alunos_com_nee:
            continue
        unidade = getattr(m.turma, "unidade", None)
        if not unidade:
            continue
        uid = unidade.id
        counter_alunos[uid].add(m.aluno_id)
        counter_turmas[uid].add(m.turma_id)
        counter_nec[uid] += nec_count_by_aluno.get(m.aluno_id, 0)
        unidades[uid] = unidade

    items = []
    for uid, aluno_ids in counter_alunos.items():
        unidade = unidades[uid]
        municipio = _get_municipio_from_unidade(unidade) or "—"
        items.append(
            {
                "municipio": municipio,
                "unidade": getattr(unidade, "nome", f"Unidade #{uid}"),
                "total_alunos": len(aluno_ids),
                "total_turmas": len(counter_turmas[uid]),
                "total_nec": counter_nec[uid],
                "url": reverse("nee:relatorios_alunos") + f"?unidade={uid}",
            }
        )
    items.sort(key=lambda x: (-x["total_alunos"], x["municipio"], x["unidade"]))

    if request.GET.get("export") in ("csv", "pdf"):
        headers = ["Município", "Unidade", "Alunos", "Turmas", "Necessidades (ativas)"]
        rows = [[i["municipio"], i["unidade"], i["total_alunos"], i["total_turmas"], i["total_nec"]] for i in items]
        if request.GET.get("export") == "csv":
            return export_csv("nee_relatorio_por_unidade.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="nee_relatorio_por_unidade.pdf",
            title="NEE — Relatório por unidade",
            headers=headers,
            rows=rows,
            subtitle="Alunos por unidade",
            filtros="Somente necessidades ativas",
        )

    actions = [
        {"label": "Voltar", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Exportar CSV", "url": reverse("nee:relatorios_por_unidade") + "?export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "Exportar PDF", "url": reverse("nee:relatorios_por_unidade") + "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]
    return render(request, "nee/relatorios/por_unidade_enterprise.html", {"items": items, "actions": actions})



@login_required
def relatorios_por_municipio(request):
    alunos_qs = scope_filter_alunos(request.user, Aluno.objects.all())

    matriculas = scope_filter_matriculas(
        request.user,
        Matricula.objects.select_related("turma", "turma__unidade").filter(aluno__in=alunos_qs),
    )

    nec_qs = AlunoNecessidade.objects.filter(aluno__in=alunos_qs, ativo=True)
    alunos_com_nee = set(nec_qs.values_list("aluno_id", flat=True).distinct())

    nec_count_by_aluno = defaultdict(int)
    for row in nec_qs.values("aluno_id").annotate(c=Count("id")):
        nec_count_by_aluno[row["aluno_id"]] = row["c"]

    muni_alunos = defaultdict(set)    # municipio -> set(aluno_id)
    muni_unidades = defaultdict(set)  # municipio -> set(unidade_id)
    muni_turmas = defaultdict(set)    # municipio -> set(turma_id)
    muni_nec = defaultdict(int)       # municipio -> total necessidades ativas somadas

    for m in matriculas:
        if m.aluno_id not in alunos_com_nee:
            continue
        unidade = getattr(m.turma, "unidade", None)
        municipio = _get_municipio_from_unidade(unidade) or "—"
        muni_alunos[municipio].add(m.aluno_id)
        if unidade:
            muni_unidades[municipio].add(unidade.id)
        muni_turmas[municipio].add(m.turma_id)
        muni_nec[municipio] += nec_count_by_aluno.get(m.aluno_id, 0)

    items = []
    for municipio, aluno_ids in muni_alunos.items():
        items.append(
            {
                "municipio": municipio,
                "total_alunos": len(aluno_ids),
                "total_unidades": len(muni_unidades[municipio]),
                "total_turmas": len(muni_turmas[municipio]),
                "total_nec": muni_nec[municipio],
                "url": reverse("nee:relatorios_alunos") + f"?municipio={municipio}",
            }
        )
    items.sort(key=lambda x: (-x["total_alunos"], x["municipio"]))

    if request.GET.get("export") in ("csv", "pdf"):
        headers = ["Município", "Alunos", "Unidades", "Turmas", "Necessidades (ativas)"]
        rows = [[i["municipio"], i["total_alunos"], i["total_unidades"], i["total_turmas"], i["total_nec"]] for i in items]
        if request.GET.get("export") == "csv":
            return export_csv("nee_relatorio_por_municipio.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="nee_relatorio_por_municipio.pdf",
            title="NEE — Relatório por município",
            headers=headers,
            rows=rows,
            subtitle="Alunos por município",
            filtros="Somente necessidades ativas",
        )

    actions = [
        {"label": "Voltar", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Exportar CSV", "url": reverse("nee:relatorios_por_municipio") + "?export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "Exportar PDF", "url": reverse("nee:relatorios_por_municipio") + "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]
    return render(request, "nee/relatorios/por_municipio_enterprise.html", {"items": items, "actions": actions})


@login_required
def relatorios_alunos(request):
    from django.core.paginator import Paginator

    alunos_qs = scope_filter_alunos(request.user, Aluno.objects.all())

    tipo_id = request.GET.get("tipo")
    unidade_id = request.GET.get("unidade")
    municipio = (request.GET.get("municipio") or "").strip()

    # filtro por tipo (necessidade ativa)
    if tipo_id:
        alunos_qs = alunos_qs.filter(necessidades__tipo_id=tipo_id, necessidades__ativo=True).distinct()

    # vamos enriquecer com matrícula (unidade/municipio/turma)
    matriculas_all = scope_filter_matriculas(
        request.user,
        Matricula.objects.select_related("turma", "turma__unidade").filter(aluno__in=alunos_qs),
    )

    # filtro por unidade/municipio via matrícula
    if unidade_id or municipio:
        alvo_ids = set()
        for m in matriculas_all:
            unidade = getattr(m.turma, "unidade", None)
            if unidade_id and str(getattr(unidade, "id", "")) != str(unidade_id):
                continue
            if municipio and (_get_municipio_from_unidade(unidade) or "—") != municipio:
                continue
            alvo_ids.add(m.aluno_id)
        alunos_qs = alunos_qs.filter(id__in=alvo_ids)

    alunos_qs = alunos_qs.order_by("nome")

    # Paginação: 10 por página
    paginator = Paginator(alunos_qs, 10)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)
    alunos = list(page_obj.object_list)

    aluno_ids = [a.id for a in alunos]

    # matrículas do page
    matriculas_page = [m for m in matriculas_all if m.aluno_id in set(aluno_ids)]

    # por aluno: (municipio, unidade, turma)
    info_by_aluno = {}
    for m in matriculas_page:
        if m.aluno_id in info_by_aluno:
            continue
        unidade = getattr(m.turma, "unidade", None)
        info_by_aluno[m.aluno_id] = {
            "municipio": _get_municipio_from_unidade(unidade) or "—",
            "unidade": getattr(unidade, "nome", "—") if unidade else "—",
            "turma": getattr(m.turma, "nome", "—") if m.turma else "—",
        }

    # necessidades do page
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

    # export (exporta o conjunto filtrado completo)
    if request.GET.get("export") in ("csv", "pdf"):
        base_qs = alunos_qs  # queryset filtrado total

        # pega até 5000 por segurança
        all_ids = list(base_qs.values_list("id", flat=True)[:5000])
        all_alunos = list(Aluno.objects.filter(id__in=all_ids).order_by("nome"))

        # mapas globais p/ export (sem paginação)
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
                "municipio": _get_municipio_from_unidade(unidade) or "—",
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

    # actions preservando filtros atuais
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