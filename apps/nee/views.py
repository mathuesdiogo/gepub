from __future__ import annotations

import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

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

    qs = TipoNecessidade.objects.all()
    if q:
        qs = qs.filter(Q(nome__icontains=q))

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "nee/tipo_list.html", {"q": q, "page_obj": page_obj})


@login_required
def tipo_detail(request, pk: int):
    tipo = get_object_or_404(TipoNecessidade, pk=pk)
    return render(request, "nee/tipo_detail.html", {"tipo": tipo})


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

    return render(request, "nee/tipo_form.html", {"form": form, "mode": "create"})


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

    return render(
        request,
        "nee/tipo_form.html",
        {"form": form, "mode": "update", "tipo": tipo},
    )


# -----------------------------
# RELATÓRIOS
# -----------------------------
@login_required
def relatorios_index(request):
    return render(request, "nee/relatorios/index.html")


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
        matriculas = matriculas.filter(situacao="ATIVA")  # se seu choice for outro, ajuste aqui

    return matriculas


def _csv_response(filename: str) -> HttpResponse:
    """
    Força download no browser (inclusive em alguns casos de Android).
    """
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    resp["X-Content-Type-Options"] = "nosniff"
    resp.write("\ufeff")  # BOM para Excel (UTF-8)
    return resp


@login_required
def relatorio_por_tipo(request):
    ano = (request.GET.get("ano") or "").strip()
    municipio_id = (request.GET.get("municipio") or "").strip()
    unidade_id = (request.GET.get("unidade") or "").strip()
    situacao = (request.GET.get("situacao") or "").strip()

    municipio_id, unidade_id = _aplicar_rbac_relatorios(request, municipio_id, unidade_id)

    matriculas = _matriculas_base()
    matriculas = _aplicar_filtros_matriculas(matriculas, ano, municipio_id, unidade_id, situacao)

    alunos_ids = matriculas.values_list("aluno_id", flat=True).distinct()

    rows = (
        AlunoNecessidade.objects
        .filter(aluno_id__in=alunos_ids, ativo=True, tipo__ativo=True)
        .values("tipo__id", "tipo__nome")
        .annotate(total=Count("aluno_id", distinct=True))
        .order_by("-total", "tipo__nome")
    )

    total_alunos_nee = (
        AlunoNecessidade.objects
        .filter(aluno_id__in=alunos_ids, ativo=True, tipo__ativo=True)
        .values("aluno_id")
        .distinct()
        .count()
    )

    municipios = Municipio.objects.filter(ativo=True).order_by("nome")
    unidades = Unidade.objects.filter(ativo=True).order_by("nome")

    if municipio_id.isdigit():
        municipios = municipios.filter(id=int(municipio_id))
        unidades = unidades.filter(secretaria__municipio_id=int(municipio_id))

    if unidade_id.isdigit():
        unidades = unidades.filter(id=int(unidade_id))

    # ✅ CSV (ANTES do render)
    if request.GET.get("format") == "csv":
        response = _csv_response("nee_por_tipo.csv")
        writer = csv.writer(response)
        writer.writerow(["Tipo de Necessidade", "Total de alunos com NEE"])
        for r in rows:
            writer.writerow([r["tipo__nome"], r["total"]])
        return response

    return render(
        request,
        "nee/relatorios/por_tipo.html",
        {
            "rows": rows,
            "ano": ano,
            "municipio_id": municipio_id,
            "unidade_id": unidade_id,
            "situacao": situacao,
            "municipios": municipios,
            "unidades": unidades,
            "total_alunos_nee": total_alunos_nee,
        },
    )


@login_required
def relatorio_por_municipio(request):
    ano = (request.GET.get("ano") or "").strip()
    municipio_id = (request.GET.get("municipio") or "").strip()
    situacao = (request.GET.get("situacao") or "").strip()

    municipio_id, _unidade_id = _aplicar_rbac_relatorios(request, municipio_id, "")

    matriculas = _matriculas_base()
    matriculas = _aplicar_filtros_matriculas(matriculas, ano, municipio_id, "", situacao)

    alunos_ids = matriculas.values_list("aluno_id", flat=True).distinct()

    total_alunos_nee = (
        AlunoNecessidade.objects
        .filter(aluno_id__in=alunos_ids, ativo=True, tipo__ativo=True)
        .values("aluno_id")
        .distinct()
        .count()
    )

    rows = (
        AlunoNecessidade.objects
        .filter(aluno_id__in=alunos_ids, ativo=True, tipo__ativo=True)
        .values(
            "aluno__matriculas__turma__unidade__secretaria__municipio__nome",
            "aluno__matriculas__turma__unidade__secretaria__municipio__uf",
        )
        .annotate(total=Count("aluno_id", distinct=True))
        .order_by(
            "-total",
            "aluno__matriculas__turma__unidade__secretaria__municipio__nome",
        )
    )

    municipios = Municipio.objects.filter(ativo=True).order_by("nome")
    if municipio_id.isdigit():
        municipios = municipios.filter(id=int(municipio_id))

    if request.GET.get("format") == "csv":
        response = _csv_response("nee_por_municipio.csv")
        writer = csv.writer(response)
        writer.writerow(["Município", "UF", "Total de alunos com NEE"])
        for r in rows:
            writer.writerow([
                r["aluno__matriculas__turma__unidade__secretaria__municipio__nome"],
                r["aluno__matriculas__turma__unidade__secretaria__municipio__uf"],
                r["total"],
            ])
        return response

    return render(
        request,
        "nee/relatorios/por_municipio.html",
        {
            "rows": rows,
            "ano": ano,
            "municipio_id": municipio_id,
            "situacao": situacao,
            "municipios": municipios,
            "total_alunos_nee": total_alunos_nee,
        },
    )


@login_required
def relatorio_por_unidade(request):
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
        .values("aluno_id")
        .distinct()
        .count()
    )

    rows = (
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

    municipios = Municipio.objects.filter(ativo=True).order_by("nome")
    unidades = Unidade.objects.filter(ativo=True).order_by("nome")

    if municipio_id.isdigit():
        municipios = municipios.filter(id=int(municipio_id))
        unidades = unidades.filter(secretaria__municipio_id=int(municipio_id))

    if unidade_id.isdigit():
        unidades = unidades.filter(id=int(unidade_id))

    if request.GET.get("format") == "csv":
        response = _csv_response("nee_por_unidade.csv")
        writer = csv.writer(response)
        writer.writerow(["Município", "Secretaria", "Unidade", "Tipo", "Total de alunos com NEE"])
        for r in rows:
            writer.writerow([
                r["aluno__matriculas__turma__unidade__secretaria__municipio__nome"],
                r["aluno__matriculas__turma__unidade__secretaria__nome"],
                r["aluno__matriculas__turma__unidade__nome"],
                r["aluno__matriculas__turma__unidade__tipo"],
                r["total"],
            ])
        return response

    return render(
        request,
        "nee/relatorios/por_unidade.html",
        {
            "rows": rows,
            "ano": ano,
            "municipio_id": municipio_id,
            "unidade_id": unidade_id,
            "situacao": situacao,
            "municipios": municipios,
            "unidades": unidades,
            "total_alunos_nee": total_alunos_nee,
        },
    )
