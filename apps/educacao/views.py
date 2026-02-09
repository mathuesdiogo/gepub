from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.decorators import require_perm
from core.rbac import (
    can,
    scope_filter_turmas,
    scope_filter_alunos,
    scope_filter_matriculas,
)

from .forms import TurmaForm, AlunoForm, MatriculaForm
from .models import Turma, Aluno, Matricula

from nee.forms import AlunoNecessidadeForm, ApoioMatriculaForm
from nee.models import AlunoNecessidade, ApoioMatricula


@login_required
@require_perm("educacao.view")
def index(request):
    return render(request, "educacao/index.html")


# -----------------------------
# TURMAS (CRUD)
# -----------------------------

@login_required
@require_perm("educacao.view")
def turma_list(request):
    q = (request.GET.get("q") or "").strip()
    ano = (request.GET.get("ano") or "").strip()

    qs = Turma.objects.select_related(
        "unidade",
        "unidade__secretaria",
        "unidade__secretaria__municipio",
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

    # ✅ RBAC (ANTES do paginator)
    qs = scope_filter_turmas(request.user, qs)

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "educacao/turma_list.html", {"q": q, "ano": ano, "page_obj": page_obj})


@login_required
@require_perm("educacao.view")
def turma_detail(request, pk: int):
    qs = Turma.objects.select_related(
        "unidade",
        "unidade__secretaria",
        "unidade__secretaria__municipio",
    )
    qs = scope_filter_turmas(request.user, qs)

    turma = get_object_or_404(qs, pk=pk)
    return render(request, "educacao/turma_detail.html", {"turma": turma})


@login_required
@require_perm("educacao.manage")
def turma_create(request):
    if request.method == "POST":
        form = TurmaForm(request.POST, user=request.user)
        if form.is_valid():
            turma = form.save()
            messages.success(request, "Turma criada com sucesso.")
            return redirect("educacao:turma_detail", pk=turma.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = TurmaForm(user=request.user)

    return render(request, "educacao/turma_form.html", {"form": form, "mode": "create"})


@login_required
@require_perm("educacao.manage")
def turma_update(request, pk: int):
    qs = Turma.objects.select_related(
        "unidade",
        "unidade__secretaria",
        "unidade__secretaria__municipio",
    )
    qs = scope_filter_turmas(request.user, qs)
    turma = get_object_or_404(qs, pk=pk)

    if request.method == "POST":
        form = TurmaForm(request.POST, instance=turma, user=request.user)
        if form.is_valid():
            turma = form.save()
            messages.success(request, "Turma atualizada com sucesso.")
            return redirect("educacao:turma_detail", pk=turma.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = TurmaForm(instance=turma, user=request.user)

    return render(request, "educacao/turma_form.html", {"form": form, "mode": "update", "turma": turma})


# -----------------------------
# ALUNOS (CRUD)
# -----------------------------

@login_required
@require_perm("educacao.view")
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

    # ✅ RBAC: aluno é por matrícula → turma → unidade
    qs = scope_filter_alunos(request.user, qs)

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "educacao/aluno_list.html", {"q": q, "page_obj": page_obj})


@login_required
@require_perm("educacao.view")
def aluno_detail(request, pk: int):
    # ✅ RBAC: o próprio aluno precisa estar no escopo
    aluno_qs = scope_filter_alunos(request.user, Aluno.objects.all())
    aluno = get_object_or_404(aluno_qs, pk=pk)

    # Matrículas do aluno (também no escopo)
    matriculas_qs = (
        Matricula.objects.select_related(
            "aluno",
            "turma",
            "turma__unidade",
            "turma__unidade__secretaria",
            "turma__unidade__secretaria__municipio",
        )
        .filter(aluno=aluno)
        .order_by("-id")
    )
    matriculas_qs = scope_filter_matriculas(request.user, matriculas_qs)
    matriculas = matriculas_qs

    # NEE do aluno (permitimos ver se o aluno está no escopo)
    necessidades = (
        AlunoNecessidade.objects.select_related("tipo")
        .filter(aluno=aluno)
        .order_by("-id")
    )

    # Apoios por matrícula (somente dentro do escopo)
    apoios_qs = (
        ApoioMatricula.objects.select_related(
            "matricula",
            "matricula__turma",
            "matricula__turma__unidade",
            "matricula__turma__unidade__secretaria",
            "matricula__turma__unidade__secretaria__municipio",
        )
        .filter(matricula__aluno=aluno)
        .order_by("-id")
    )
    # scope via matrículas
    allowed_matriculas = scope_filter_matriculas(request.user, Matricula.objects.filter(aluno=aluno)).values_list("id", flat=True)
    apoios = apoios_qs.filter(matricula_id__in=allowed_matriculas)

    # -------------------------
    # Ações (POST) na mesma tela
    # -------------------------
    if request.method == "POST":
        action = (request.POST.get("_action") or "").strip()

        # Ações que alteram dados exigem manage
        if action in {"add_matricula", "add_nee", "add_apoio"} and not can(request.user, "educacao.manage"):
            return HttpResponseForbidden("403 — Você não tem permissão para alterar dados de Educação.")

        # 1) adicionar matrícula
        if action == "add_matricula":
            form_matricula = MatriculaForm(request.POST, user=request.user)
            form_nee = AlunoNecessidadeForm(request.POST, aluno=aluno)
            form_apoio = ApoioMatriculaForm(aluno=aluno)

            if form_matricula.is_valid():
                m = form_matricula.save(commit=False)
                m.aluno = aluno

                # ✅ RBAC: turma escolhida tem que estar no escopo
                turma_ok = scope_filter_turmas(request.user, Turma.objects.filter(pk=m.turma_id)).exists()
                if not turma_ok:
                    return HttpResponseForbidden("403 — Turma fora do seu escopo.")

                if not m.data_matricula:
                    m.data_matricula = timezone.localdate()
                m.save()
                messages.success(request, "Matrícula adicionada com sucesso.")
                return redirect("educacao:aluno_detail", pk=aluno.pk)

            messages.error(request, "Corrija os erros da matrícula.")

        # 2) adicionar necessidade (NEE)
        elif action == "add_nee":
            form_matricula = MatriculaForm(user=request.user)
            form_nee = AlunoNecessidadeForm(request.POST, aluno=aluno)
            form_apoio = ApoioMatriculaForm(aluno=aluno)

            if form_nee.is_valid():
                nee = form_nee.save(commit=False)
                nee.aluno = aluno
                nee.save()
                messages.success(request, "Necessidade adicionada com sucesso.")
                return redirect("educacao:aluno_detail", pk=aluno.pk)

            messages.error(request, "Corrija os erros da necessidade.")

        # 3) adicionar apoio por matrícula
        elif action == "add_apoio":
            form_matricula = MatriculaForm(user=request.user)
            form_nee = AlunoNecessidadeForm(aluno=aluno)
            form_apoio = ApoioMatriculaForm(request.POST, aluno=aluno)

            if form_apoio.is_valid():
                apoio = form_apoio.save(commit=False)

                # ✅ RBAC: matrícula selecionada precisa estar no escopo
                matricula_ok = scope_filter_matriculas(
                    request.user,
                    Matricula.objects.filter(pk=apoio.matricula_id, aluno=aluno),
                ).exists()
                if not matricula_ok:
                    return HttpResponseForbidden("403 — Matrícula fora do seu escopo.")

                apoio.save()
                messages.success(request, "Apoio adicionado com sucesso.")
                return redirect("educacao:aluno_detail", pk=aluno.pk)

            messages.error(request, "Corrija os erros do apoio.")

        else:
            # ação desconhecida: mantém forms vazios
            form_matricula = MatriculaForm(user=request.user)
            form_nee = AlunoNecessidadeForm(request.POST, aluno=aluno)
            form_apoio = ApoioMatriculaForm(aluno=aluno)
            messages.error(request, "Ação inválida.")

    else:
        # GET: forms vazios
        form_matricula = MatriculaForm(user=request.user)
        form_nee = AlunoNecessidadeForm(aluno=aluno)
        form_apoio = ApoioMatriculaForm(aluno=aluno)

    return render(
        request,
        "educacao/aluno_detail.html",
        {
            "aluno": aluno,
            "matriculas": matriculas,
            "form_matricula": form_matricula,
            "necessidades": necessidades,
            "form_nee": form_nee,
            "apoios": apoios,
            "form_apoio": form_apoio,
        },
    )


@login_required
@require_perm("educacao.manage")
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
@require_perm("educacao.manage")
def aluno_update(request, pk: int):
    # ✅ RBAC: só edita aluno que está no escopo (via matrículas)
    aluno_qs = scope_filter_alunos(request.user, Aluno.objects.all())
    aluno = get_object_or_404(aluno_qs, pk=pk)

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
