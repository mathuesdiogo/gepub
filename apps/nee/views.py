from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from django.db.models import Count
from educacao.models import Matricula
from .models import AlunoNecessidade


from .forms import TipoNecessidadeForm
from .models import TipoNecessidade

from org.models import Municipio, Unidade



@login_required
def index(request):
    return render(request, "nee/index.html")


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

@login_required
def relatorios_index(request):
    return render(request, "nee/relatorios/index.html")


@login_required
def relatorio_por_tipo(request):
    ano = (request.GET.get("ano") or "").strip()
    municipio_id = (request.GET.get("municipio") or "").strip()
    unidade_id = (request.GET.get("unidade") or "").strip()

    matriculas = Matricula.objects.select_related(
        "aluno",
        "turma",
        "turma__unidade",
        "turma__unidade__secretaria",
        "turma__unidade__secretaria__municipio",
    )

    if ano.isdigit():
        matriculas = matriculas.filter(turma__ano_letivo=int(ano))

    if municipio_id.isdigit():
        matriculas = matriculas.filter(turma__unidade__secretaria__municipio_id=int(municipio_id))

    if unidade_id.isdigit():
        matriculas = matriculas.filter(turma__unidade_id=int(unidade_id))

    alunos_ids = matriculas.values_list("aluno_id", flat=True).distinct()

    # conta alunos com NEE por tipo
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

    return render(
        request,
        "nee/relatorios/por_tipo.html",
        {
            "rows": rows,
            "ano": ano,
            "municipio_id": municipio_id,
            "unidade_id": unidade_id,
            "total_alunos_nee": total_alunos_nee,
        },
    )
@login_required
def relatorio_por_municipio(request):
    ano = (request.GET.get("ano") or "").strip()
    municipio_id = (request.GET.get("municipio") or "").strip()

    matriculas = Matricula.objects.select_related(
        "aluno",
        "turma",
        "turma__unidade",
        "turma__unidade__secretaria",
        "turma__unidade__secretaria__municipio",
    )

    if ano.isdigit():
        matriculas = matriculas.filter(turma__ano_letivo=int(ano))

    if municipio_id.isdigit():
        matriculas = matriculas.filter(turma__unidade__secretaria__municipio_id=int(municipio_id))

    alunos_ids = matriculas.values_list("aluno_id", flat=True).distinct()

    # total de alunos com NEE no filtro
    total_alunos_nee = (
        AlunoNecessidade.objects
        .filter(aluno_id__in=alunos_ids, ativo=True, tipo__ativo=True)
        .values("aluno_id")
        .distinct()
        .count()
    )

    # agrupa por município (contando alunos distintos)
    rows = (
        AlunoNecessidade.objects
        .filter(aluno_id__in=alunos_ids, ativo=True, tipo__ativo=True)
        .values("aluno__matriculas__turma__unidade__secretaria__municipio__id",
                "aluno__matriculas__turma__unidade__secretaria__municipio__nome",
                "aluno__matriculas__turma__unidade__secretaria__municipio__uf")
        .annotate(total=Count("aluno_id", distinct=True))
        .order_by("-total",
                  "aluno__matriculas__turma__unidade__secretaria__municipio__nome")
    )

    municipios = Municipio.objects.filter(ativo=True).order_by("nome")

    return render(
        request,
        "nee/relatorios/por_municipio.html",
        {
            "rows": rows,
            "ano": ano,
            "municipio_id": municipio_id,
            "municipios": municipios,
            "total_alunos_nee": total_alunos_nee,
        },
    )


@login_required
def relatorio_por_unidade(request):
    ano = (request.GET.get("ano") or "").strip()
    municipio_id = (request.GET.get("municipio") or "").strip()
    unidade_id = (request.GET.get("unidade") or "").strip()

    matriculas = Matricula.objects.select_related(
        "aluno",
        "turma",
        "turma__unidade",
        "turma__unidade__secretaria",
        "turma__unidade__secretaria__municipio",
    )

    if ano.isdigit():
        matriculas = matriculas.filter(turma__ano_letivo=int(ano))

    if municipio_id.isdigit():
        matriculas = matriculas.filter(turma__unidade__secretaria__municipio_id=int(municipio_id))

    if unidade_id.isdigit():
        matriculas = matriculas.filter(turma__unidade_id=int(unidade_id))

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
            "aluno__matriculas__turma__unidade__id",
            "aluno__matriculas__turma__unidade__nome",
            "aluno__matriculas__turma__unidade__tipo",
            "aluno__matriculas__turma__unidade__secretaria__nome",
            "aluno__matriculas__turma__unidade__secretaria__municipio__nome",
        )
        .annotate(total=Count("aluno_id", distinct=True))
        .order_by("-total", "aluno__matriculas__turma__unidade__nome")
    )

    municipios = Municipio.objects.filter(ativo=True).order_by("nome")

    unidades = Unidade.objects.filter(ativo=True).order_by("nome")
    if municipio_id.isdigit():
        unidades = unidades.filter(secretaria__municipio_id=int(municipio_id))

    return render(
        request,
        "nee/relatorios/por_unidade.html",
        {
            "rows": rows,
            "ano": ano,
            "municipio_id": municipio_id,
            "unidade_id": unidade_id,
            "municipios": municipios,
            "unidades": unidades,
            "total_alunos_nee": total_alunos_nee,
        },
    )
