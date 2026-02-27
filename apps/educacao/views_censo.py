from __future__ import annotations

from io import BytesIO
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from apps.core.decorators import require_perm
from apps.core.exports import export_csv
from apps.core.rbac import scope_filter_alunos, scope_filter_matriculas, scope_filter_turmas, scope_filter_unidades
from apps.org.models import Unidade

from .censo_layouts import (
    DATASET_CHOICES,
    SUPPORTED_LAYOUTS,
    build_layout_validation_rows,
    resolve_dataset,
    resolve_layout,
)
from .models import Aluno, Matricula, Turma


def _clean_param(v: str | None) -> str:
    v = (v or "").strip()
    return "" if v.lower() in {"none", "null", "undefined"} else v


def _normalize_year(v: str, fallback: int) -> int:
    return int(v) if v.isdigit() else fallback


def _render_xlsx(filename: str, title: str, headers: list[str], rows: list[list[str]]):
    try:
        from openpyxl import Workbook  # type: ignore
    except Exception:
        return None

    wb = Workbook()
    ws = wb.active
    ws.title = "Censo"
    ws.append([title])
    ws.append([])
    ws.append(headers)
    for r in rows:
        ws.append(r)

    buffer = BytesIO()
    wb.save(buffer)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _dataset_escolas(*, unidades_qs):
    headers = ["Código INEP", "Unidade", "Secretaria", "Município", "UF", "Ativa"]
    rows = []
    for u in unidades_qs.order_by("nome"):
        sec = getattr(u, "secretaria", None)
        mun = getattr(sec, "municipio", None)
        rows.append(
            [
                u.codigo_inep or "",
                u.nome or "",
                getattr(sec, "nome", "") or "",
                getattr(mun, "nome", "") or "",
                getattr(mun, "uf", "") or "",
                "Sim" if u.ativo else "Não",
            ]
        )
    return headers, rows, "Censo Escolar - Escolas"


def _dataset_turmas(*, turmas_qs):
    headers = [
        "Turma",
        "Ano Letivo",
        "Turno",
        "Modalidade",
        "Etapa",
        "Forma Oferta",
        "Curso",
        "Classe Especial",
        "Bilíngue Surdos",
        "Unidade",
        "Código INEP Unidade",
        "Matrículas Ativas",
    ]
    rows = []
    qs = turmas_qs.annotate(
        total_ativas=Count(
            "matriculas",
            filter=Q(matriculas__situacao=Matricula.Situacao.ATIVA),
        )
    ).order_by("nome")
    for t in qs:
        unidade = getattr(t, "unidade", None)
        rows.append(
            [
                t.nome or "",
                str(t.ano_letivo or ""),
                t.get_turno_display() if hasattr(t, "get_turno_display") else (t.turno or ""),
                t.get_modalidade_display() if hasattr(t, "get_modalidade_display") else (t.modalidade or ""),
                t.get_etapa_display() if hasattr(t, "get_etapa_display") else (t.etapa or ""),
                t.get_forma_oferta_display() if hasattr(t, "get_forma_oferta_display") else (t.forma_oferta or ""),
                getattr(getattr(t, "curso", None), "nome", "") or "",
                "Sim" if getattr(t, "classe_especial", False) else "Não",
                "Sim" if getattr(t, "bilingue_surdos", False) else "Não",
                getattr(unidade, "nome", "") or "",
                getattr(unidade, "codigo_inep", "") or "",
                str(getattr(t, "total_ativas", 0)),
            ]
        )
    return headers, rows, "Censo Escolar - Turmas"


def _dataset_matriculas(*, matriculas_qs):
    headers = ["Aluno", "CPF", "NIS", "Turma", "Ano Letivo", "Unidade", "Situação", "Data Matrícula"]
    rows = []
    qs = matriculas_qs.order_by("aluno__nome", "turma__nome")
    for m in qs:
        aluno = getattr(m, "aluno", None)
        turma = getattr(m, "turma", None)
        unidade = getattr(turma, "unidade", None) if turma else None
        rows.append(
            [
                getattr(aluno, "nome", "") or "",
                getattr(aluno, "cpf", "") or "",
                getattr(aluno, "nis", "") or "",
                getattr(turma, "nome", "") or "",
                str(getattr(turma, "ano_letivo", "") or ""),
                getattr(unidade, "nome", "") or "",
                m.get_situacao_display() if hasattr(m, "get_situacao_display") else (m.situacao or ""),
                m.data_matricula.strftime("%d/%m/%Y") if getattr(m, "data_matricula", None) else "",
            ]
        )
    return headers, rows, "Censo Escolar - Matrículas"


def _dataset_alunos(*, alunos_qs):
    headers = ["Aluno", "CPF", "NIS", "Data Nascimento", "Nome da Mãe", "Telefone", "Ativo"]
    rows = []
    for a in alunos_qs.order_by("nome"):
        rows.append(
            [
                a.nome or "",
                a.cpf or "",
                a.nis or "",
                a.data_nascimento.strftime("%d/%m/%Y") if a.data_nascimento else "",
                a.nome_mae or "",
                a.telefone or "",
                "Sim" if a.ativo else "Não",
            ]
        )
    return headers, rows, "Censo Escolar - Alunos"


def _dataset_docentes(*, docentes_qs):
    headers = ["Usuário", "Nome", "E-mail", "Turmas Vinculadas"]
    rows = []
    for d in docentes_qs.order_by("username"):
        rows.append(
            [
                d.username or "",
                d.get_full_name() or "",
                d.email or "",
                str(getattr(d, "total_turmas", 0)),
            ]
        )
    return headers, rows, "Censo Escolar - Docentes"


def _build_dataset(dataset: str, *, unidades_qs, turmas_qs, matriculas_qs, alunos_qs, docentes_qs):
    if dataset == "escolas":
        return _dataset_escolas(unidades_qs=unidades_qs)
    if dataset == "turmas":
        return _dataset_turmas(turmas_qs=turmas_qs)
    if dataset == "alunos":
        return _dataset_alunos(alunos_qs=alunos_qs)
    if dataset == "docentes":
        return _dataset_docentes(docentes_qs=docentes_qs)
    return _dataset_matriculas(matriculas_qs=matriculas_qs)


@login_required
@require_perm("educacao.view")
def censo_escolar(request):
    now_year = timezone.now().year
    ano = _normalize_year(_clean_param(request.GET.get("ano")), now_year)

    requested_layout = _normalize_year(_clean_param(request.GET.get("layout")), ano)
    layout = resolve_layout(requested_layout, ano)

    requested_dataset = (_clean_param(request.GET.get("dataset")) or "matriculas").lower()
    dataset = resolve_dataset(requested_dataset)

    unidade_id = _clean_param(request.GET.get("unidade"))
    export = _clean_param(request.GET.get("export")).lower()

    if requested_layout != layout:
        messages.warning(request, f"Layout {requested_layout} não suportado. Usando layout {layout}.")
    if requested_dataset != dataset:
        messages.warning(request, f"Dataset '{requested_dataset}' inválido. Usando '{dataset}'.")

    unidades_options_qs = scope_filter_unidades(
        request.user,
        Unidade.objects.select_related("secretaria", "secretaria__municipio")
        .filter(tipo=Unidade.Tipo.EDUCACAO)
        .order_by("nome"),
    )
    unidades_qs = unidades_options_qs

    turmas_qs = scope_filter_turmas(
        request.user,
        Turma.objects.select_related("unidade", "unidade__secretaria", "unidade__secretaria__municipio", "curso"),
    ).filter(ano_letivo=ano)

    if unidade_id.isdigit() and unidades_options_qs.filter(pk=int(unidade_id)).exists():
        turmas_qs = turmas_qs.filter(unidade_id=int(unidade_id))
        unidades_qs = unidades_qs.filter(pk=int(unidade_id))
    else:
        unidade_id = ""

    matriculas_qs = scope_filter_matriculas(
        request.user,
        Matricula.objects.select_related(
            "aluno",
            "turma",
            "turma__unidade",
            "turma__unidade__secretaria",
            "turma__unidade__secretaria__municipio",
        ),
    ).filter(turma__in=turmas_qs)

    aluno_ids = matriculas_qs.values_list("aluno_id", flat=True).distinct()
    alunos_qs = scope_filter_alunos(request.user, Aluno.objects.filter(pk__in=aluno_ids))

    User = get_user_model()
    docentes_qs = (
        User.objects.filter(turmas_ministradas__in=turmas_qs)
        .distinct()
        .annotate(total_turmas=Count("turmas_ministradas", distinct=True))
    )

    headers_export, rows_export, title_export = _build_dataset(
        dataset,
        unidades_qs=unidades_qs,
        turmas_qs=turmas_qs,
        matriculas_qs=matriculas_qs,
        alunos_qs=alunos_qs,
        docentes_qs=docentes_qs,
    )

    if export in {"csv", "xlsx"}:
        ext = "csv" if export == "csv" else "xlsx"
        filename = f"censo_{layout}_{dataset}.{ext}"
        if export == "csv":
            return export_csv(filename, headers_export, rows_export)

        response = _render_xlsx(filename, title_export, headers_export, rows_export)
        if response is not None:
            return response
        messages.error(
            request,
            "Exportação XLSX indisponível no ambiente atual (instale a dependência openpyxl).",
        )

    total_unidades = unidades_qs.count()
    total_turmas = turmas_qs.count()
    total_matriculas = matriculas_qs.count()
    total_alunos = alunos_qs.count()
    total_docentes = docentes_qs.count()

    inconsistencias = {
        "unidades_sem_inep": unidades_qs.filter(codigo_inep="").count(),
        "alunos_sem_cpf": alunos_qs.filter(cpf_last4="").count(),
        "alunos_sem_nascimento": alunos_qs.filter(data_nascimento__isnull=True).count(),
        "turmas_sem_docente": turmas_qs.filter(professores__isnull=True).distinct().count(),
        "turmas_sem_modalidade": turmas_qs.filter(Q(modalidade__isnull=True) | Q(modalidade="")).count(),
        "turmas_sem_etapa": turmas_qs.filter(Q(etapa__isnull=True) | Q(etapa="")).count(),
    }

    ctx_validacao = {
        "matriculas_qs": matriculas_qs,
        "alunos_qs": alunos_qs,
        "turmas_qs": turmas_qs,
        "unidades_qs": unidades_qs,
        "docentes_qs": docentes_qs,
    }
    rows_layout_validacao = build_layout_validation_rows(layout, dataset, ctx=ctx_validacao)

    qbase = {
        "ano": ano,
        "layout": layout,
        "dataset": dataset,
    }
    if unidade_id:
        qbase["unidade"] = unidade_id

    def qjoin(**extra):
        params = dict(qbase)
        params.update(extra)
        return f"?{urlencode(params)}"

    actions = [
        {
            "label": "Exportar CSV",
            "url": qjoin(export="csv"),
            "icon": "fa-solid fa-file-csv",
            "variant": "btn--ghost",
        },
        {
            "label": "Exportar XLSX",
            "url": qjoin(export="xlsx"),
            "icon": "fa-solid fa-file-excel",
            "variant": "btn--ghost",
        },
    ]

    dataset_options_html = "".join(
        [
            f'<option value="{k}" {"selected" if dataset == k else ""}>{label}</option>'
            for (k, label) in DATASET_CHOICES
        ]
    )
    unidade_options_html = "".join(
        [
            f'<option value="{u.id}" {"selected" if str(u.id) == str(unidade_id) else ""}>{u.nome}</option>'
            for u in unidades_options_qs
        ]
    )

    extra_filters = f"""
    <div class=\"filter-bar__field\">
      <label>Ano Letivo</label>
      <input type=\"number\" name=\"ano\" value=\"{ano}\" min=\"2000\" max=\"2100\" />
    </div>
    <div class=\"filter-bar__field\">
      <label>Layout Censo</label>
      <input type=\"number\" name=\"layout\" value=\"{layout}\" min=\"2000\" max=\"2100\" />
    </div>
    <div class=\"filter-bar__field\">
      <label>Unidade</label>
      <select name=\"unidade\">
        <option value=\"\">Todas</option>
        {unidade_options_html}
      </select>
    </div>
    <div class=\"filter-bar__field\">
      <label>Dataset</label>
      <select name=\"dataset\">
        {dataset_options_html}
      </select>
    </div>
    """

    headers_consistencia = [
        {"label": "Validação"},
        {"label": "Pendências", "width": "140px"},
    ]
    rows_consistencia = [
        {"cells": [{"text": "Unidades sem código INEP"}, {"text": str(inconsistencias["unidades_sem_inep"])}]},
        {"cells": [{"text": "Alunos sem CPF preenchido"}, {"text": str(inconsistencias["alunos_sem_cpf"])}]},
        {"cells": [{"text": "Alunos sem data de nascimento"}, {"text": str(inconsistencias["alunos_sem_nascimento"])}]},
        {"cells": [{"text": "Turmas sem docente vinculado"}, {"text": str(inconsistencias["turmas_sem_docente"])}]},
        {"cells": [{"text": "Turmas sem modalidade preenchida"}, {"text": str(inconsistencias["turmas_sem_modalidade"])}]},
        {"cells": [{"text": "Turmas sem etapa preenchida"}, {"text": str(inconsistencias["turmas_sem_etapa"])}]},
    ]

    headers_layout_validacao = [
        {"label": "Regra de layout"},
        {"label": "Pendências", "width": "140px"},
        {"label": "Status", "width": "120px"},
    ]

    headers_preview = [{"label": h} for h in headers_export]
    rows_preview = [{"cells": [{"text": c} for c in row]} for row in rows_export[:20]]
    preview_subtitle = f"Mostrando até 20 linhas ({len(rows_export)} no total)"
    layouts_suportados = ", ".join(str(x) for x in SUPPORTED_LAYOUTS)

    return render(
        request,
        "educacao/censo_index.html",
        {
            "actions": actions,
            "action_url": reverse("educacao:censo_escolar"),
            "clear_url": reverse("educacao:censo_escolar"),
            "has_filters": bool(unidade_id or dataset != "matriculas" or int(layout) != int(ano)),
            "extra_filters": extra_filters,
            "ano": ano,
            "layout": layout,
            "dataset": dataset,
            "total_unidades": total_unidades,
            "total_turmas": total_turmas,
            "total_matriculas": total_matriculas,
            "total_alunos": total_alunos,
            "total_docentes": total_docentes,
            "headers_consistencia": headers_consistencia,
            "rows_consistencia": rows_consistencia,
            "headers_layout_validacao": headers_layout_validacao,
            "rows_layout_validacao": rows_layout_validacao,
            "headers_preview": headers_preview,
            "rows_preview": rows_preview,
            "preview_total": len(rows_export),
            "preview_subtitle": preview_subtitle,
            "layouts_suportados": layouts_suportados,
        },
    )
