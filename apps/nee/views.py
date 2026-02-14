from __future__ import annotations

import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe
from weasyprint import HTML

from core.rbac import get_profile, is_admin
from educacao.models import Matricula
from org.models import Municipio, Unidade

from .forms import TipoNecessidadeForm
from .models import AlunoNecessidade, TipoNecessidade


@login_required
def index(request):
    return render(request, "nee/index.html")


# -----------------------------
# TIPOS DE NECESSIDADE (CRUD)
# -----------------------------
@login_required
def tipo_list(request):
    q = (request.GET.get("q") or "").strip()

    qs = TipoNecessidade.objects.all().order_by("nome")
    if q:
        qs = qs.filter(Q(nome__icontains=q))

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    actions = [
        {"label": "Voltar", "url": reverse("nee:index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Novo tipo", "url": reverse("nee:tipo_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"},
    ]

    headers = [
        {"label": "Nome"},
        {"label": "Ativo", "width": "110px"},
    ]

    rows = []
    for t in page_obj.object_list:
        rows.append({
            "cells": [
                {"text": t.nome, "url": reverse("nee:tipo_detail", args=[t.pk])},
                {"text": "Sim" if t.ativo else "Não", "url": ""},
            ],
            "can_edit": False,
            "edit_url": "",
        })

    action_url = reverse("nee:tipo_list")
    clear_url = reverse("nee:tipo_list")
    has_filters = bool(q)

    return render(request, "nee/tipo_list.html", {
        "q": q,
        "page_obj": page_obj,
        "actions": actions,
        "headers": headers,
        "rows": rows,
        "action_url": action_url,
        "clear_url": clear_url,
        "has_filters": has_filters,
        "extra_filters": "",
    })


@login_required
def tipo_detail(request, pk: int):
    tipo = get_object_or_404(TipoNecessidade, pk=pk)

    actions = [
        {"label": "Voltar", "url": reverse("nee:tipo_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Editar", "url": reverse("nee:tipo_update", args=[tipo.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"},
    ]

    fields = [
        {"label": "Nome", "value": tipo.nome},
    ]
    pills = [
        {"label": "Status", "value": "Ativo" if tipo.ativo else "Inativo", "variant": "success" if tipo.ativo else "danger"},
    ]

    return render(request, "nee/tipo_detail.html", {
        "tipo": tipo,
        "actions": actions,
        "page_title": tipo.nome,
        "page_subtitle": "Detalhes do tipo de necessidade",
        "fields": fields,
        "pills": pills,
    })


@login_required
def tipo_create(request):
    if request.method == "POST":
        form = TipoNecessidadeForm(request.POST)
        if form.is_valid():
            tipo = form.save()
            messages.success(request, "Tipo de necessidade criado com sucesso.")
            return redirect("nee:tipo_detail", pk=tipo.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = TipoNecessidadeForm()

    actions = [{"label": "Voltar", "url": reverse("nee:tipo_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    return render(request, "nee/tipo_form.html", {"form": form, "mode": "create", "actions": actions})


@login_required
def tipo_update(request, pk: int):
    tipo = get_object_or_404(TipoNecessidade, pk=pk)

    if request.method == "POST":
        form = TipoNecessidadeForm(request.POST, instance=tipo)
        if form.is_valid():
            form.save()
            messages.success(request, "Tipo de necessidade atualizado com sucesso.")
            return redirect("nee:tipo_detail", pk=tipo.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = TipoNecessidadeForm(instance=tipo)

    actions = [{"label": "Voltar", "url": reverse("nee:tipo_detail", args=[tipo.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    return render(request, "nee/tipo_form.html", {"form": form, "mode": "update", "tipo": tipo, "actions": actions})


# -----------------------------
# RELATÓRIOS
# -----------------------------
@login_required
def relatorios_index(request):
    actions = [
        {"label": "Voltar", "url": reverse("nee:index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
    ]
    return render(request, "nee/relatorios/index.html", {"actions": actions})


def _aplicar_rbac_relatorios(request, municipio_id: str, unidade_id: str):
    """
    Força os filtros de município/unidade com base no Profile do usuário.
    Admin vê tudo.
    """
    if is_admin(request.user):
        return municipio_id, unidade_id

    p = get_profile(request.user)
    if p and p.ativo:
        if p.municipio_id:
            municipio_id = str(p.municipio_id)

        if p.role == "UNIDADE" and p.unidade_id:
            unidade_id = str(p.unidade_id)

    return municipio_id, unidade_id


def _matriculas_base():
    return Matricula.objects.select_related(
        "aluno",
        "turma",
        "turma__unidade",
        "turma__unidade__secretaria",
        "turma__unidade__secretaria__municipio",
    )


def _aplicar_filtros_matriculas(matriculas, ano: str, municipio_id: str, unidade_id: str, situacao: str):
    if ano.isdigit():
        matriculas = matriculas.filter(turma__ano_letivo=int(ano))

    if municipio_id.isdigit():
        matriculas = matriculas.filter(turma__unidade__secretaria__municipio_id=int(municipio_id))

    if unidade_id.isdigit():
        matriculas = matriculas.filter(turma__unidade_id=int(unidade_id))

    # ✅ Situação (padrão: ATIVA)
    if situacao:
        matriculas = matriculas.filter(situacao=situacao)
    else:
        matriculas = matriculas.filter(situacao="ATIVA")

    return matriculas


def _csv_response(filename: str) -> HttpResponse:
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    resp["X-Content-Type-Options"] = "nosniff"
    resp.write("\ufeff")  # BOM para Excel (UTF-8)
    return resp


def _pdf_response(request, *, template: str, filename: str, context: dict) -> HttpResponse:
    from django.templatetags.static import static
    logo_url = request.build_absolute_uri(static("img/logo_prefeitura.png"))
    context = {**context, "logo_url": logo_url}

    html = render_to_string(template, context, request=request)
    pdf_bytes = HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()

    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    resp["X-Content-Type-Options"] = "nosniff"
    return resp


def _build_extra_filters_html(*, ano: str, municipio_id: str, unidade_id: str, situacao: str, municipios, unidades):
    parts = []

    # Ano (input)
    parts.append(
        f'<div class="filter-bar__field"><label class="small">Ano</label>'
        f'<input name="ano" value="{escape(ano)}" placeholder="Ex: 2026" /></div>'
    )

    # Município (select) — usa partial existente
    parts.append(render_to_string("core/partials/filter_select.html", {
        "label": "Município",
        "name": "municipio",
        "value": municipio_id,
        "empty_label": "Todos",
        "options": [{"value": str(m.id), "label": m.nome} for m in municipios],
    }))

    # Unidade (select)
    parts.append(render_to_string("core/partials/filter_select.html", {
        "label": "Unidade",
        "name": "unidade",
        "value": unidade_id,
        "empty_label": "Todas",
        "options": [{"value": str(u.id), "label": u.nome} for u in unidades],
    }))

    # Situação (select)
    parts.append(render_to_string("core/partials/filter_select.html", {
        "label": "Situação",
        "name": "situacao",
        "value": situacao,
        "empty_label": "ATIVA (padrão)",
        "options": [
            {"value": "ATIVA", "label": "ATIVA"},
            {"value": "INATIVA", "label": "INATIVA"},
        ],
    }))

    return mark_safe("".join(parts))


@login_required
def relatorio_por_tipo(request):
    q = (request.GET.get("q") or "").strip()
    ano = (request.GET.get("ano") or "").strip()
    municipio_id = (request.GET.get("municipio") or "").strip()
    unidade_id = (request.GET.get("unidade") or "").strip()
    situacao = (request.GET.get("situacao") or "").strip()

    municipio_id, unidade_id = _aplicar_rbac_relatorios(request, municipio_id, unidade_id)

    matriculas = _matriculas_base()
    matriculas = _aplicar_filtros_matriculas(matriculas, ano, municipio_id, unidade_id, situacao)
    alunos_ids = matriculas.values_list("aluno_id", flat=True).distinct()

    qs_rows = (
        AlunoNecessidade.objects
        .filter(aluno_id__in=alunos_ids, ativo=True, tipo__ativo=True)
        .values("tipo__id", "tipo__nome")
        .annotate(total=Count("aluno_id", distinct=True))
        .order_by("-total", "tipo__nome")
    )
    if q:
        qs_rows = qs_rows.filter(Q(tipo__nome__icontains=q))

    total_alunos_nee = (
        AlunoNecessidade.objects
        .filter(aluno_id__in=alunos_ids, ativo=True, tipo__ativo=True)
        .values("aluno_id").distinct().count()
    )

    # CSV
    if request.GET.get("format") == "csv":
        response = _csv_response("nee_por_tipo.csv")
        writer = csv.writer(response)
        writer.writerow(["Tipo de Necessidade", "Total de alunos com NEE"])
        for r in qs_rows:
            writer.writerow([r["tipo__nome"], r["total"]])
        return response

    # PDF
    if request.GET.get("format") == "pdf":
        filtros = f"Ano={ano or '-'} | Município={municipio_id or '-'} | Unidade={unidade_id or '-'} | Situação={situacao or 'ATIVA'}"
        return _pdf_response(
            request,
            template="nee/relatorios/pdf/por_tipo.html",
            filename="nee_por_tipo.pdf",
            context={
                "prefeitura_nome": "Prefeitura Municipal",
                "municipio_nome": (Municipio.objects.filter(id=int(municipio_id)).values_list("nome", flat=True).first() if municipio_id.isdigit() else ""),
                "municipio_uf": (Municipio.objects.filter(id=int(municipio_id)).values_list("uf", flat=True).first() if municipio_id.isdigit() else ""),
                "title": "Relatório NEE — Por tipo",
                "generated_at": timezone.localtime().strftime("%d/%m/%Y %H:%M"),
                "filtros": filtros,
                "rows": qs_rows,
                "total_alunos_nee": total_alunos_nee,
            },
        )

    paginator = Paginator(list(qs_rows), 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    headers = [
        {"label": "Tipo de necessidade"},
        {"label": "Total de alunos", "width": "160px"},
    ]
    rows = [{
        "cells": [{"text": r["tipo__nome"], "url": ""}, {"text": str(r["total"]), "url": ""}],
        "can_edit": False,
        "edit_url": "",
    } for r in page_obj.object_list]

    action_url = reverse("nee:relatorio_por_tipo")
    clear_url = reverse("nee:relatorio_por_tipo")
    has_filters = bool(q or ano or municipio_id or unidade_id or situacao)

    municipios = Municipio.objects.filter(ativo=True).order_by("nome")
    unidades = Unidade.objects.filter(ativo=True).order_by("nome")
    if municipio_id.isdigit():
        municipios = municipios.filter(id=int(municipio_id))
        unidades = unidades.filter(secretaria__municipio_id=int(municipio_id))
    if unidade_id.isdigit():
        unidades = unidades.filter(id=int(unidade_id))

    extra_filters = _build_extra_filters_html(
        ano=ano, municipio_id=municipio_id, unidade_id=unidade_id, situacao=situacao,
        municipios=municipios, unidades=unidades,
    )

    base_qs = request.GET.copy()
    base_qs.pop("format", None)
    csv_url = f"{reverse('nee:relatorio_por_tipo')}?{base_qs.urlencode()}&format=csv" if base_qs else f"{reverse('nee:relatorio_por_tipo')}?format=csv"
    pdf_url = f"{reverse('nee:relatorio_por_tipo')}?{base_qs.urlencode()}&format=pdf" if base_qs else f"{reverse('nee:relatorio_por_tipo')}?format=pdf"

    actions = [
        {"label": "Voltar", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "CSV", "url": csv_url, "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "PDF", "url": pdf_url, "icon": "fa-solid fa-file-pdf", "variant": "btn-primary"},
    ]

    summary_fields = [
        {"label": "Ano", "value": ano or "—"},
        {"label": "Município", "value": municipio_id or "—"},
        {"label": "Unidade", "value": unidade_id or "—"},
        {"label": "Situação", "value": situacao or "ATIVA"},
    ]
    summary_pills = [{"label": "Alunos com NEE", "value": str(total_alunos_nee), "variant": "info"}]

    return render(request, "nee/relatorios/por_tipo.html", {
        "actions": actions,
        "q": q,
        "headers": headers,
        "rows": rows,
        "page_obj": page_obj,
        "action_url": action_url,
        "clear_url": clear_url,
        "has_filters": has_filters,
        "extra_filters": extra_filters,
        "summary_fields": summary_fields,
        "summary_pills": summary_pills,
        "total_alunos_nee": total_alunos_nee,
    })


@login_required
def relatorio_por_unidade(request):
    q = (request.GET.get("q") or "").strip()
    ano = (request.GET.get("ano") or "").strip()
    municipio_id = (request.GET.get("municipio") or "").strip()
    unidade_id = (request.GET.get("unidade") or "").strip()
    situacao = (request.GET.get("situacao") or "").strip()

    municipio_id, unidade_id = _aplicar_rbac_relatorios(request, municipio_id, unidade_id)

    matriculas = _matriculas_base()
    matriculas = _aplicar_filtros_matriculas(matriculas, ano, municipio_id, unidade_id, situacao)
    alunos_ids = matriculas.values_list("aluno_id", flat=True).distinct()

    total_alunos_nee = (
        AlunoNecessidade.objects
        .filter(aluno_id__in=alunos_ids, ativo=True, tipo__ativo=True)
        .values("aluno_id").distinct().count()
    )

    qs_rows = (
        AlunoNecessidade.objects
        .filter(aluno_id__in=alunos_ids, ativo=True, tipo__ativo=True)
        .values(
            "aluno__matriculas__turma__unidade__secretaria__municipio__nome",
            "aluno__matriculas__turma__unidade__secretaria__nome",
            "aluno__matriculas__turma__unidade__nome",
            "aluno__matriculas__turma__unidade__tipo",
        )
        .annotate(total=Count("aluno_id", distinct=True))
        .order_by("-total", "aluno__matriculas__turma__unidade__nome")
    )

    if q:
        qs_rows = qs_rows.filter(
            Q(aluno__matriculas__turma__unidade__nome__icontains=q)
            | Q(aluno__matriculas__turma__unidade__secretaria__nome__icontains=q)
            | Q(aluno__matriculas__turma__unidade__secretaria__municipio__nome__icontains=q)
        )

    # CSV
    if request.GET.get("format") == "csv":
        response = _csv_response("nee_por_unidade.csv")
        writer = csv.writer(response)
        writer.writerow(["Município", "Secretaria", "Unidade", "Tipo", "Total de alunos com NEE"])
        for r in qs_rows:
            writer.writerow([
                r["aluno__matriculas__turma__unidade__secretaria__municipio__nome"],
                r["aluno__matriculas__turma__unidade__secretaria__nome"],
                r["aluno__matriculas__turma__unidade__nome"],
                r["aluno__matriculas__turma__unidade__tipo"],
                r["total"],
            ])
        return response

    # PDF
    if request.GET.get("format") == "pdf":
        filtros = f"Ano={ano or '-'} | Município={municipio_id or '-'} | Unidade={unidade_id or '-'} | Situação={situacao or 'ATIVA'}"
        return _pdf_response(
            request,
            template="nee/relatorios/pdf/por_unidade.html",
            filename="nee_por_unidade.pdf",
            context={
                "prefeitura_nome": "Prefeitura Municipal",
                "municipio_nome": (Municipio.objects.filter(id=int(municipio_id)).values_list("nome", flat=True).first() if municipio_id.isdigit() else ""),
                "municipio_uf": (Municipio.objects.filter(id=int(municipio_id)).values_list("uf", flat=True).first() if municipio_id.isdigit() else ""),
                "secretaria_nome": (Unidade.objects.filter(id=int(unidade_id)).values_list("secretaria__nome", flat=True).first() if unidade_id.isdigit() else ""),
                "title": "Relatório NEE — Por unidade",
                "generated_at": timezone.localtime().strftime("%d/%m/%Y %H:%M"),
                "filtros": filtros,
                "rows": qs_rows,
                "total_alunos_nee": total_alunos_nee,
            },
        )

    paginator = Paginator(list(qs_rows), 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    headers = [
        {"label": "Município"},
        {"label": "Secretaria"},
        {"label": "Unidade"},
        {"label": "Tipo", "width": "130px"},
        {"label": "Total", "width": "110px"},
    ]
    rows = [{
        "cells": [
            {"text": r["aluno__matriculas__turma__unidade__secretaria__municipio__nome"], "url": ""},
            {"text": r["aluno__matriculas__turma__unidade__secretaria__nome"], "url": ""},
            {"text": r["aluno__matriculas__turma__unidade__nome"], "url": ""},
            {"text": str(r["aluno__matriculas__turma__unidade__tipo"]), "url": ""},
            {"text": str(r["total"]), "url": ""},
        ],
        "can_edit": False,
        "edit_url": "",
    } for r in page_obj.object_list]

    action_url = reverse("nee:relatorio_por_unidade")
    clear_url = reverse("nee:relatorio_por_unidade")
    has_filters = bool(q or ano or municipio_id or unidade_id or situacao)

    municipios = Municipio.objects.filter(ativo=True).order_by("nome")
    unidades = Unidade.objects.filter(ativo=True).order_by("nome")
    if municipio_id.isdigit():
        municipios = municipios.filter(id=int(municipio_id))
        unidades = unidades.filter(secretaria__municipio_id=int(municipio_id))
    if unidade_id.isdigit():
        unidades = unidades.filter(id=int(unidade_id))

    extra_filters = _build_extra_filters_html(
        ano=ano, municipio_id=municipio_id, unidade_id=unidade_id, situacao=situacao,
        municipios=municipios, unidades=unidades,
    )

    base_qs = request.GET.copy()
    base_qs.pop("format", None)
    csv_url = f"{reverse('nee:relatorio_por_unidade')}?{base_qs.urlencode()}&format=csv" if base_qs else f"{reverse('nee:relatorio_por_unidade')}?format=csv"
    pdf_url = f"{reverse('nee:relatorio_por_unidade')}?{base_qs.urlencode()}&format=pdf" if base_qs else f"{reverse('nee:relatorio_por_unidade')}?format=pdf"

    actions = [
        {"label": "Voltar", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "CSV", "url": csv_url, "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "PDF", "url": pdf_url, "icon": "fa-solid fa-file-pdf", "variant": "btn-primary"},
    ]

    summary_fields = [
        {"label": "Ano", "value": ano or "—"},
        {"label": "Município", "value": municipio_id or "—"},
        {"label": "Unidade", "value": unidade_id or "—"},
        {"label": "Situação", "value": situacao or "ATIVA"},
    ]
    summary_pills = [{"label": "Alunos com NEE", "value": str(total_alunos_nee), "variant": "info"}]

    return render(request, "nee/relatorios/por_unidade.html", {
        "actions": actions,
        "q": q,
        "headers": headers,
        "rows": rows,
        "page_obj": page_obj,
        "action_url": action_url,
        "clear_url": clear_url,
        "has_filters": has_filters,
        "extra_filters": extra_filters,
        "summary_fields": summary_fields,
        "summary_pills": summary_pills,
        "total_alunos_nee": total_alunos_nee,
    })


@login_required
def relatorio_por_municipio(request):
    from django.core.exceptions import PermissionDenied
    if not is_admin(request.user):
        raise PermissionDenied

    qs = Municipio.objects.filter(ativo=True).order_by("nome")

    rows_raw = []
    for m in qs:
        total = (
            AlunoNecessidade.objects
            .filter(aluno__matriculas__turma__unidade__secretaria__municipio=m, ativo=True, tipo__ativo=True)
            .values("aluno").distinct().count()
        )
        rows_raw.append((m.nome, total))

    # CSV
    if request.GET.get("format") == "csv":
        response = _csv_response("nee_por_municipio.csv")
        w = csv.writer(response)
        w.writerow(["Município", "Total de alunos com NEE"])
        for nome, total in rows_raw:
            w.writerow([nome, total])
        return response

    # PDF
    if request.GET.get("format") == "pdf":
        return _pdf_response(
            request,
            template="nee/relatorios/pdf/por_municipio.html",
            filename="nee_por_municipio.pdf",
            context={
                "title": "Relatório NEE — Por município",
                "generated_at": timezone.localtime().strftime("%d/%m/%Y %H:%M"),
                "rows": [{"municipio": nome, "total": total} for nome, total in rows_raw],
            },
        )

    headers = [
        {"label": "Município"},
        {"label": "Total de alunos com NEE", "width": "220px"},
    ]
    rows = [{
        "cells": [{"text": nome, "url": ""}, {"text": str(total), "url": ""}],
        "can_edit": False,
        "edit_url": "",
    } for nome, total in rows_raw]

    csv_url = f"{reverse('nee:relatorio_por_municipio')}?format=csv"
    pdf_url = f"{reverse('nee:relatorio_por_municipio')}?format=pdf"

    actions = [
        {"label": "Voltar", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "CSV", "url": csv_url, "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "PDF", "url": pdf_url, "icon": "fa-solid fa-file-pdf", "variant": "btn-primary"},
    ]

    return render(request, "nee/relatorios/por_municipio.html", {
        "actions": actions,
        "headers": headers,
        "rows": rows,
        "page_obj": None,
        "q": "",
    })
