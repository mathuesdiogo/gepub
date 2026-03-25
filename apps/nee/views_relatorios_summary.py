from __future__ import annotations

from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from apps.core.exports import export_csv, export_pdf_table
from apps.core.rbac import scope_filter_alunos, scope_filter_matriculas
from apps.educacao.models import Aluno, Matricula

from .models import AcompanhamentoNEE, AlunoNecessidade
from .views_relatorios_common import get_municipio_from_unidade


@login_required
def relatorios_index(request):
    actions = [{"label": "Voltar", "url": reverse("nee:index"), "icon": "fa-solid fa-arrow-left", "variant": "gp-button--ghost"}]
    cards = [
        {"title": "Por tipo", "description": "Distribuição de alunos por tipo de necessidade.", "icon": "fa-solid fa-tags", "url": reverse("nee:relatorios_por_tipo")},
        {"title": "Por município", "description": "Distribuição por município (com base nas unidades/turmas).", "icon": "fa-solid fa-city", "url": reverse("nee:relatorios_por_municipio")},
        {"title": "Por unidade", "description": "Distribuição por unidade escolar.", "icon": "fa-solid fa-school", "url": reverse("nee:relatorios_por_unidade")},
        {
            "title": "Capacidade de atendimento",
            "description": "Alunos ativos por profissional (janela de 90 dias).",
            "icon": "fa-solid fa-users-gear",
            "url": reverse("nee:relatorios_capacidade"),
        },
    ]
    return render(request, "nee/relatorios/index_enterprise.html", {"actions": actions, "cards": cards})


@login_required
def relatorios_por_tipo(request):
    alunos_qs = scope_filter_alunos(request.user, Aluno.objects.all())

    nec_qs = (
        AlunoNecessidade.objects.filter(aluno__in=alunos_qs, ativo=True)
        .select_related("tipo", "aluno")
    )

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
        if m.aluno_id not in aluno_unidade:
            aluno_unidade[m.aluno_id] = getattr(unidade, "id", None)
        if m.aluno_id not in aluno_municipio:
            aluno_municipio[m.aluno_id] = get_municipio_from_unidade(unidade) or "—"

    by_tipo = {}
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
        {"label": "Voltar", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "gp-button--ghost"},
        {"label": "Exportar CSV", "url": reverse("nee:relatorios_por_tipo") + "?export=csv", "icon": "fa-solid fa-file-csv", "variant": "gp-button--ghost"},
        {"label": "Exportar PDF", "url": reverse("nee:relatorios_por_tipo") + "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "gp-button--ghost"},
    ]
    return render(request, "nee/relatorios/por_tipo_enterprise.html", {"items": items, "actions": actions})


@login_required
def relatorios_por_unidade(request):
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

    counter_alunos = defaultdict(set)
    counter_turmas = defaultdict(set)
    counter_nec = defaultdict(int)
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
        municipio = get_municipio_from_unidade(unidade) or "—"
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
        {"label": "Voltar", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "gp-button--ghost"},
        {"label": "Exportar CSV", "url": reverse("nee:relatorios_por_unidade") + "?export=csv", "icon": "fa-solid fa-file-csv", "variant": "gp-button--ghost"},
        {"label": "Exportar PDF", "url": reverse("nee:relatorios_por_unidade") + "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "gp-button--ghost"},
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

    muni_alunos = defaultdict(set)
    muni_unidades = defaultdict(set)
    muni_turmas = defaultdict(set)
    muni_nec = defaultdict(int)

    for m in matriculas:
        if m.aluno_id not in alunos_com_nee:
            continue
        unidade = getattr(m.turma, "unidade", None)
        municipio = get_municipio_from_unidade(unidade) or "—"
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
        {"label": "Voltar", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "gp-button--ghost"},
        {"label": "Exportar CSV", "url": reverse("nee:relatorios_por_municipio") + "?export=csv", "icon": "fa-solid fa-file-csv", "variant": "gp-button--ghost"},
        {"label": "Exportar PDF", "url": reverse("nee:relatorios_por_municipio") + "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "gp-button--ghost"},
    ]
    return render(request, "nee/relatorios/por_municipio_enterprise.html", {"items": items, "actions": actions})


@login_required
def relatorios_capacidade(request):
    alunos_qs = scope_filter_alunos(request.user, Aluno.objects.all())
    matriculas = scope_filter_matriculas(
        request.user,
        Matricula.objects.select_related("turma", "turma__unidade").filter(aluno__in=alunos_qs),
    )
    necessidade_aluno_ids = set(
        AlunoNecessidade.objects.filter(aluno__in=alunos_qs, ativo=True).values_list("aluno_id", flat=True).distinct()
    )
    if not necessidade_aluno_ids:
        return render(
            request,
            "nee/relatorios/capacidade_enterprise.html",
            {
                "items": [],
                "actions": [
                    {
                        "label": "Voltar",
                        "url": reverse("nee:relatorios_index"),
                        "icon": "fa-solid fa-arrow-left",
                        "variant": "gp-button--ghost",
                    }
                ],
            },
        )

    alunos_por_unidade = defaultdict(set)
    unidade_nome = {}
    unidade_municipio = {}
    aluno_unidade_ids = defaultdict(set)
    for m in matriculas:
        if m.aluno_id not in necessidade_aluno_ids:
            continue
        unidade = getattr(m.turma, "unidade", None)
        if not unidade:
            continue
        uid = unidade.id
        alunos_por_unidade[uid].add(m.aluno_id)
        aluno_unidade_ids[m.aluno_id].add(uid)
        unidade_nome[uid] = unidade.nome
        unidade_municipio[uid] = get_municipio_from_unidade(unidade) or "—"

    janela_dias = 90
    corte = timezone.localdate() - timezone.timedelta(days=janela_dias)
    acompanhamentos = (
        AcompanhamentoNEE.objects.filter(aluno_id__in=necessidade_aluno_ids, data__gte=corte)
        .values("aluno_id", "autor_id")
    )
    profissionais_por_unidade = defaultdict(set)
    for row in acompanhamentos:
        aluno_id = row["aluno_id"]
        autor_id = row["autor_id"]
        if not autor_id:
            continue
        for uid in aluno_unidade_ids.get(aluno_id, set()):
            profissionais_por_unidade[uid].add(autor_id)

    items = []
    for uid, alunos_ids in alunos_por_unidade.items():
        total_alunos = len(alunos_ids)
        total_profissionais = len(profissionais_por_unidade.get(uid, set()))
        razao = 0.0
        if total_profissionais > 0:
            razao = round(total_alunos / total_profissionais, 2)
        items.append(
            {
                "municipio": unidade_municipio.get(uid, "—"),
                "unidade": unidade_nome.get(uid, f"Unidade #{uid}"),
                "total_alunos": total_alunos,
                "profissionais_ativos": total_profissionais,
                "alunos_por_profissional": razao,
                "janela_dias": janela_dias,
                "url": reverse("nee:relatorios_alunos") + f"?unidade={uid}",
            }
        )
    items.sort(key=lambda i: (-i["total_alunos"], i["unidade"]))

    if request.GET.get("export") in ("csv", "pdf"):
        headers = ["Município", "Unidade", "Alunos NEE ativos", "Profissionais ativos (90d)", "Razão alunos/profissional"]
        rows = [
            [
                i["municipio"],
                i["unidade"],
                i["total_alunos"],
                i["profissionais_ativos"],
                i["alunos_por_profissional"],
            ]
            for i in items
        ]
        if request.GET.get("export") == "csv":
            return export_csv("nee_relatorio_capacidade.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="nee_relatorio_capacidade.pdf",
            title="NEE — Capacidade de Atendimento",
            headers=headers,
            rows=rows,
            subtitle="Alunos ativos por profissional (janela 90 dias)",
            filtros="Somente alunos com necessidade ativa",
        )

    actions = [
        {"label": "Voltar", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "gp-button--ghost"},
        {"label": "Exportar CSV", "url": reverse("nee:relatorios_capacidade") + "?export=csv", "icon": "fa-solid fa-file-csv", "variant": "gp-button--ghost"},
        {"label": "Exportar PDF", "url": reverse("nee:relatorios_capacidade") + "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "gp-button--ghost"},
    ]
    return render(request, "nee/relatorios/capacidade_enterprise.html", {"items": items, "actions": actions})
