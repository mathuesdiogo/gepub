from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import TurmaForm, AlunoForm, MatriculaForm
from .models import Turma, Aluno, Matricula


@login_required
def index(request):
    return render(request, "educacao/index.html")


@login_required
def turma_list(request):
    q = (request.GET.get("q") or "").strip()
    ano = (request.GET.get("ano") or "").strip()

    qs = Turma.objects.select_related("unidade", "unidade__secretaria", "unidade__secretaria__municipio")

    if ano.isdigit():
        qs = qs.filter(ano_letivo=int(ano))

    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(unidade__nome__icontains=q)
            | Q(unidade__secretaria__nome__icontains=q)
            | Q(unidade__secretaria__municipio__nome__icontains=q)
        )

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "educacao/turma_list.html",
        {"q": q, "ano": ano, "page_obj": page_obj},
    )


@login_required
def turma_detail(request, pk: int):
    turma = get_object_or_404(
        Turma.objects.select_related("unidade", "unidade__secretaria", "unidade__secretaria__municipio"),
        pk=pk,
    )
    return render(request, "educacao/turma_detail.html", {"turma": turma})


@login_required
def turma_create(request):
    if request.method == "POST":
        form = TurmaForm(request.POST)
        if form.is_valid():
            turma = form.save()
            messages.success(request, "Turma criada com sucesso.")
            return redirect("educacao:turma_detail", pk=turma.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = TurmaForm()

    return render(request, "educacao/turma_form.html", {"form": form, "mode": "create"})


@login_required
def turma_update(request, pk: int):
    turma = get_object_or_404(Turma, pk=pk)

    if request.method == "POST":
        form = TurmaForm(request.POST, instance=turma)
        if form.is_valid():
            form.save()
            messages.success(request, "Turma atualizada com sucesso.")
            return redirect("educacao:turma_detail", pk=turma.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = TurmaForm(instance=turma)

    return render(request, "educacao/turma_form.html", {"form": form, "mode": "update", "turma": turma})

# -----------------------------
# ALUNOS (CRUD)
# -----------------------------

@login_required
def aluno_list(request):
    q = (request.GET.get("q") or "").strip()

    qs = Aluno.objects.all()
    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(cpf__icontains=q)
            | Q(nis__icontains=q)
            | Q(nome_mae__icontains=q)
        )

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "educacao/aluno_list.html", {"q": q, "page_obj": page_obj})


@login_required
def aluno_detail(request, pk: int):
    aluno = get_object_or_404(Aluno, pk=pk)

    # lista de matrículas do aluno
    matriculas = (
        Matricula.objects
        .select_related("turma", "turma__unidade", "turma__unidade__secretaria", "turma__unidade__secretaria__municipio")
        .filter(aluno=aluno)
        .order_by("-id")
    )

    # form de matrícula dentro da página
    if request.method == "POST" and request.POST.get("_action") == "add_matricula":
        form_matricula = MatriculaForm(request.POST)
        if form_matricula.is_valid():
            m = form_matricula.save(commit=False)
            m.aluno = aluno
            m.save()
            messages.success(request, "Matrícula adicionada com sucesso.")
            return redirect("educacao:aluno_detail", pk=aluno.pk)
        messages.error(request, "Corrija os erros da matrícula.")
    else:
        form_matricula = MatriculaForm()

    return render(
        request,
        "educacao/aluno_detail.html",
        {"aluno": aluno, "matriculas": matriculas, "form_matricula": form_matricula},
    )


@login_required
def aluno_create(request):
    if request.method == "POST":
        form = AlunoForm(request.POST)
        if form.is_valid():
            aluno = form.save()
            messages.success(request, "Aluno criado com sucesso.")
            return redirect("educacao:aluno_detail", pk=aluno.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AlunoForm()

    return render(request, "educacao/aluno_form.html", {"form": form, "mode": "create"})


@login_required
def aluno_update(request, pk: int):
    aluno = get_object_or_404(Aluno, pk=pk)

    if request.method == "POST":
        form = AlunoForm(request.POST, instance=aluno)
        if form.is_valid():
            form.save()
            messages.success(request, "Aluno atualizado com sucesso.")
            return redirect("educacao:aluno_detail", pk=aluno.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AlunoForm(instance=aluno)

    return render(
        request,
        "educacao/aluno_form.html",
        {"form": form, "mode": "update", "aluno": aluno},
    )
