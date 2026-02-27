from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.html import escape

from apps.accounts.models import Profile
from apps.core.exports import export_csv, export_pdf_table
from apps.core.rbac import can, scope_filter_turmas

from .models import Matricula, Turma


def turma_list(request):
    q = (request.GET.get("q") or "").strip()
    ano = (request.GET.get("ano") or "").strip()

    qs = (
        Turma.objects.select_related(
            "unidade",
            "unidade__secretaria",
            "unidade__secretaria__municipio",
        )
        .only(
            "id",
            "nome",
            "ano_letivo",
            "turno",
            "ativo",
            "unidade_id",
            "unidade__nome",
            "unidade__secretaria__nome",
            "unidade__secretaria__municipio__nome",
        )
    )

    if ano.isdigit():
        qs = qs.filter(ano_letivo=int(ano))

    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(unidade__nome__icontains=q)
            | Q(unidade__secretaria__nome__icontains=q)
            | Q(unidade__secretaria__municipio__nome__icontains=q)
        )

    qs = scope_filter_turmas(request.user, qs)

    export = (request.GET.get("export") or "").strip().lower()
    if export in ("csv", "pdf"):
        turmas_export = qs.order_by("-ano_letivo", "nome")

        headers_export = ["Turma", "Ano", "Turno", "Unidade", "Secretaria", "Município", "Ativo"]

        rows_export = []
        for t in turmas_export:
            rows_export.append(
                [
                    t.nome or "—",
                    str(t.ano_letivo or "—"),
                    t.get_turno_display() if hasattr(t, "get_turno_display") else (getattr(t, "turno", "") or "—"),
                    getattr(getattr(t, "unidade", None), "nome", "—"),
                    getattr(getattr(getattr(t, "unidade", None), "secretaria", None), "nome", "—"),
                    getattr(getattr(getattr(getattr(t, "unidade", None), "secretaria", None), "municipio", None), "nome", "—"),
                    "Sim" if getattr(t, "ativo", False) else "Não",
                ]
            )

        if export == "csv":
            return export_csv("turmas.csv", headers_export, rows_export)

        filtros = f"Ano={ano or '-'} | Busca={q or '-'}"
        return export_pdf_table(
            request,
            filename="turmas.pdf",
            title="Relatório — Turmas",
            headers=headers_export,
            rows=rows_export,
            filtros=filtros,
        )

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    can_edu_manage = can(request.user, "educacao.manage")

    qs_query = []
    if q:
        qs_query.append(f"q={q}")
    if ano:
        qs_query.append(f"ano={ano}")
    base_query = "&".join(qs_query)

    def qjoin(extra: str) -> str:
        return f"?{base_query + ('&' if base_query else '')}{extra}"

    actions = [
        {"label": "Exportar CSV", "url": qjoin("export=csv"), "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "Exportar PDF", "url": qjoin("export=pdf"), "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]
    if can_edu_manage:
        actions.append(
            {
                "label": "Nova Turma",
                "url": reverse("educacao:turma_create"),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            }
        )

    headers = [
        {"label": "Turma"},
        {"label": "Ano", "width": "110px"},
        {"label": "Turno", "width": "140px"},
        {"label": "Unidade"},
        {"label": "Secretaria"},
    ]

    rows = []
    for t in page_obj:
        rows.append(
            {
                "cells": [
                    {"text": t.nome, "url": reverse("educacao:turma_detail", args=[t.pk])},
                    {"text": str(t.ano_letivo or "—")},
                    {"text": t.get_turno_display() if hasattr(t, "get_turno_display") else "—"},
                    {"text": getattr(getattr(t, "unidade", None), "nome", "—")},
                    {"text": getattr(getattr(t, "unidade", None), "secretaria", None).nome if getattr(getattr(t, "unidade", None), "secretaria", None) else "—"},
                ],
                "can_edit": bool(can_edu_manage and t.pk),
                "edit_url": reverse("educacao:turma_update", args=[t.pk]) if t.pk else "",
            }
        )

    extra_filters = f"""
      <div class="filter-bar__field">
        <label class="small">Ano letivo</label>
        <input name="ano" value="{escape(ano)}" placeholder="Ex.: 2026" />
      </div>
    """

    return render(
        request,
        "educacao/turma_list.html",
        {
            "q": q,
            "ano": ano,
            "page_obj": page_obj,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "action_url": reverse("educacao:turma_list"),
            "clear_url": reverse("educacao:turma_list"),
            "has_filters": bool(ano),
            "extra_filters": extra_filters,
            "autocomplete_url": reverse("educacao:api_turmas_suggest"),
            "autocomplete_href": reverse("educacao:turma_list") + "?q={q}",
        },
    )


def turma_detail(request, pk: int):
    turma_qs = scope_filter_turmas(
        request.user,
        Turma.objects.select_related(
            "unidade",
            "unidade__secretaria",
            "unidade__secretaria__municipio",
            "curso",
        ),
    )
    turma = get_object_or_404(turma_qs, pk=pk)

    can_edu_manage = can(request.user, "educacao.manage")
    role = (getattr(getattr(request.user, "profile", None), "role", "") or "").upper()
    is_professor = role == "PROFESSOR"

    actions = [{"label": "Voltar", "url": reverse("educacao:turma_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if is_professor:
        actions.extend(
            [
                {"label": "Diário", "url": reverse("educacao:meus_diarios"), "icon": "fa-solid fa-book", "variant": "btn--ghost"},
                {"label": "Boletim", "url": reverse("educacao:boletim_turma", args=[turma.pk]), "icon": "fa-solid fa-clipboard-list", "variant": "btn--ghost"},
            ]
        )
    else:
        actions.extend(
            [
                {"label": "Horário", "url": reverse("educacao:horario_turma", args=[turma.pk]), "icon": "fa-solid fa-calendar-days", "variant": "btn--ghost"},
                {"label": "Boletim", "url": reverse("educacao:boletim_turma", args=[turma.pk]), "icon": "fa-solid fa-clipboard-list", "variant": "btn--ghost"},
                {"label": "Fechamento", "url": reverse("educacao:fechamento_turma_periodo", args=[turma.pk]), "icon": "fa-solid fa-check-double", "variant": "btn--ghost"},
                {"label": "Relatório", "url": reverse("educacao:relatorio_geral_turma", args=[turma.pk]), "icon": "fa-solid fa-file-lines", "variant": "btn--ghost"},
            ]
        )
    if can_edu_manage:
        actions.append({"label": "Editar", "url": reverse("educacao:turma_update", args=[turma.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})

    matriculas_qs = Matricula.objects.filter(turma_id=turma.id).select_related("aluno").order_by("aluno__nome")

    alunos = [m.aluno for m in matriculas_qs]
    alunos_total = len(alunos)

    alunos_ativos = Matricula.objects.filter(turma_id=turma.id, aluno__ativo=True).values("aluno_id").distinct().count()
    alunos_inativos = Matricula.objects.filter(turma_id=turma.id, aluno__ativo=False).values("aluno_id").distinct().count()

    professores = []
    professores_total = 0
    if any(getattr(f, "name", None) == "unidade" for f in Profile._meta.get_fields()):
        professores_qs = Profile.objects.filter(unidade_id=turma.unidade_id, role="PROFESSOR").select_related("user").order_by("user__username")
        professores = professores_qs
        professores_total = professores_qs.count()

    necessidades_rows = list(
        Matricula.objects.filter(
            turma_id=turma.id,
            aluno__necessidades__ativo=True,
            aluno__necessidades__tipo__ativo=True,
        )
        .values("aluno__necessidades__tipo__nome")
        .annotate(total=Count("aluno_id", distinct=True))
        .order_by("-total", "aluno__necessidades__tipo__nome")
    )

    nee_labels = [r["aluno__necessidades__tipo__nome"] for r in necessidades_rows]
    nee_values = [r["total"] for r in necessidades_rows]

    evol_rows = list(
        Turma.objects.filter(unidade_id=turma.unidade_id, nome=turma.nome)
        .values("ano_letivo")
        .annotate(total=Count("matriculas__aluno_id", distinct=True))
        .order_by("ano_letivo")
    )
    evol_labels = [str(r["ano_letivo"]) for r in evol_rows]
    evol_values = [r["total"] for r in evol_rows]

    headers_alunos = [{"label": "Nome"}, {"label": "CPF", "width": "180px"}, {"label": "Ativo", "width": "110px"}]
    rows_alunos = []
    for a in alunos:
        rows_alunos.append(
            {
                "cells": [
                    {"text": a.nome, "url": reverse("educacao:aluno_detail", args=[a.pk])},
                    {"text": getattr(a, "cpf", None) or "—", "url": ""},
                    {"text": "Sim" if getattr(a, "ativo", False) else "Não", "url": ""},
                ],
                "can_edit": False,
                "edit_url": "",
            }
        )

    headers_professores = [{"label": "Usuário"}, {"label": "Perfil"}]
    rows_professores = []
    for p in professores:
        rows_professores.append(
            {
                "cells": [
                    {"text": getattr(getattr(p, "user", None), "username", "—") or "—", "url": ""},
                    {"text": getattr(p, "role", "") or "—", "url": ""},
                ],
                "can_edit": False,
                "edit_url": "",
            }
        )

    ctx = {
        "turma": turma,
        "fields": [
            {"label": "Unidade", "value": getattr(getattr(turma, "unidade", None), "nome", "—")},
            {"label": "Ano letivo", "value": turma.ano_letivo},
            {"label": "Turno", "value": turma.get_turno_display() if hasattr(turma, "get_turno_display") else turma.turno},
            {"label": "Modalidade", "value": turma.get_modalidade_display() if hasattr(turma, "get_modalidade_display") else turma.modalidade},
            {"label": "Etapa", "value": turma.get_etapa_display() if hasattr(turma, "get_etapa_display") else turma.etapa},
            {"label": "Curso", "value": getattr(getattr(turma, "curso", None), "nome", "—")},
            {"label": "Oferta", "value": turma.get_forma_oferta_display() if hasattr(turma, "get_forma_oferta_display") else turma.forma_oferta},
        ],
        "pills": [
            {"label": "Classe especial", "value": "Sim" if getattr(turma, "classe_especial", False) else "Não"},
            {"label": "Bilíngue surdos", "value": "Sim" if getattr(turma, "bilingue_surdos", False) else "Não"},
            {"label": "Status", "value": "Ativa" if turma.ativo else "Inativa"},
        ],
        "can_edu_manage": can_edu_manage,
        "actions": actions,
        "alunos_total": alunos_total,
        "professores_total": professores_total,
        "alunos_ativos": alunos_ativos,
        "alunos_inativos": alunos_inativos,
        "nee_labels": nee_labels,
        "nee_values": nee_values,
        "status_labels": ["Ativos", "Inativos"],
        "status_values": [alunos_ativos, alunos_inativos],
        "evol_labels": evol_labels,
        "evol_values": evol_values,
        "headers_alunos": headers_alunos,
        "rows_alunos": rows_alunos,
        "headers_professores": headers_professores,
        "rows_professores": rows_professores,
    }

    return render(request, "educacao/turma_detail.html", ctx)
