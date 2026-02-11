from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.db.models import Count
from accounts.models import Profile
from core.rbac import scope_filter_turmas
from educacao.models import Turma, Matricula
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, render

from accounts.models import Profile
from core.rbac import scope_filter_turmas
from educacao.models import Turma, Matricula
from core.decorators import require_perm
from core.rbac import (
    can,
    scope_filter_turmas,
    scope_filter_alunos,
    scope_filter_matriculas,
)

from .forms import TurmaForm, AlunoForm, MatriculaForm, AlunoCreateComTurmaForm
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

    qs = scope_filter_turmas(request.user, qs)

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "educacao/turma_list.html", {"q": q, "ano": ano, "page_obj": page_obj})



@require_perm("educacao.view")
@login_required
def turma_detail(request, pk):
    # ✅ RBAC
    turma_qs = scope_filter_turmas(
        request.user,
        Turma.objects.select_related(
            "unidade",
            "unidade__secretaria",
            "unidade__secretaria__municipio",
        )
    )
    turma = get_object_or_404(turma_qs, pk=pk)

    # ========= Matrículas / Alunos =========
    matriculas_qs = (
        Matricula.objects
        .filter(turma_id=turma.id)
        .select_related("aluno")
        .order_by("aluno__nome")
    )

    alunos = [m.aluno for m in matriculas_qs]
    alunos_total = len(alunos)

    alunos_ativos = (
        Matricula.objects
        .filter(turma_id=turma.id, aluno__ativo=True)
        .values("aluno_id").distinct().count()
    )
    alunos_inativos = (
        Matricula.objects
        .filter(turma_id=turma.id, aluno__ativo=False)
        .values("aluno_id").distinct().count()
    )

    # ========= Professores (por unidade) =========
    professores = []
    professores_total = 0
    if any(getattr(f, "name", None) == "unidade" for f in Profile._meta.get_fields()):
        professores_qs = (
            Profile.objects
            .filter(unidade_id=turma.unidade_id, role="PROFESSOR")
            .select_related("user")
            .order_by("user__username")
        )
        professores = professores_qs
        professores_total = professores_qs.count()

    # ========= Gráfico NEE: por tipo de necessidade (corrigido) =========
    # Seu model: AlunoNecessidade(aluno -> related_name="necessidades", tipo -> TipoNecessidade.nome)
    necessidades_rows = list(
        Matricula.objects
        .filter(
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

    # ========= Gráfico: evolução por ano letivo =========
    # compara turmas com mesmo nome + mesma unidade
    evol_rows = list(
        Turma.objects
        .filter(unidade_id=turma.unidade_id, nome=turma.nome)
        .values("ano_letivo")
        .annotate(total=Count("matriculas__aluno_id", distinct=True))
        .order_by("ano_letivo")
    )
    evol_labels = [str(r["ano_letivo"]) for r in evol_rows]
    evol_values = [r["total"] for r in evol_rows]

    ctx = {
        "turma": turma,

        # KPIs
        "alunos_total": alunos_total,
        "professores_total": professores_total,
        "alunos_ativos": alunos_ativos,
        "alunos_inativos": alunos_inativos,

        # Listas
        "alunos": alunos,
        "professores": professores,

        # Charts (listas python p/ json_script)
        "nee_labels": nee_labels,
        "nee_values": nee_values,
        "status_labels": ["Ativos", "Inativos"],
        "status_values": [alunos_ativos, alunos_inativos],
        "evol_labels": evol_labels,
        "evol_values": evol_values,
    }

    return render(request, "educacao/turma_detail.html", ctx)



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

    qs = scope_filter_alunos(request.user, qs)

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "educacao/aluno_list.html", {"q": q, "page_obj": page_obj})


@login_required
@require_perm("educacao.view")
def aluno_detail(request, pk: int):
    aluno_qs = scope_filter_alunos(request.user, Aluno.objects.all())

    try:
        aluno = get_object_or_404(aluno_qs, pk=pk)
    except Http404:
        # ✅ caso especial continua existindo (não atrapalha):
        recent = request.session.get("recent_alunos", [])
        if pk in recent and can(request.user, "educacao.manage"):
            aluno = get_object_or_404(Aluno.objects.all(), pk=pk)
            if Matricula.objects.filter(aluno=aluno).exists():
                raise
        else:
            raise

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

    necessidades = (
        AlunoNecessidade.objects.select_related("tipo")
        .filter(aluno=aluno)
        .order_by("-id")
    )

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
    allowed_matriculas = scope_filter_matriculas(
        request.user, Matricula.objects.filter(aluno=aluno)
    ).values_list("id", flat=True)
    apoios = apoios_qs.filter(matricula_id__in=allowed_matriculas)

    if request.method == "POST":
        action = (request.POST.get("_action") or "").strip()

        if action in {"add_matricula", "add_nee", "add_apoio"} and not can(request.user, "educacao.manage"):
            return HttpResponseForbidden("403 — Você não tem permissão para alterar dados de Educação.")

        if action == "add_matricula":
            form_matricula = MatriculaForm(request.POST, user=request.user)
            form_nee = AlunoNecessidadeForm(request.POST, aluno=aluno)
            form_apoio = ApoioMatriculaForm(aluno=aluno)

            if form_matricula.is_valid():
                m = form_matricula.save(commit=False)
                m.aluno = aluno

                turma_ok = scope_filter_turmas(request.user, Turma.objects.filter(pk=m.turma_id)).exists()
                if not turma_ok:
                    return HttpResponseForbidden("403 — Turma fora do seu escopo.")

                if not m.data_matricula:
                    m.data_matricula = timezone.localdate()
                m.save()

                recent = request.session.get("recent_alunos", [])
                if aluno.pk in recent:
                    recent.remove(aluno.pk)
                    request.session["recent_alunos"] = recent
                    request.session.modified = True

                messages.success(request, "Matrícula adicionada com sucesso.")
                return redirect("educacao:aluno_detail", pk=aluno.pk)

            messages.error(request, "Corrija os erros da matrícula.")

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

        elif action == "add_apoio":
            form_matricula = MatriculaForm(user=request.user)
            form_nee = AlunoNecessidadeForm(aluno=aluno)
            form_apoio = ApoioMatriculaForm(request.POST, aluno=aluno)

            if form_apoio.is_valid():
                apoio = form_apoio.save(commit=False)

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
            form_matricula = MatriculaForm(user=request.user)
            form_nee = AlunoNecessidadeForm(request.POST, aluno=aluno)
            form_apoio = ApoioMatriculaForm(aluno=aluno)
            messages.error(request, "Ação inválida.")
    else:
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
    """
    ✅ Novo fluxo: cria o aluno e já matricula em uma turma do escopo do usuário.
    Isso elimina 404 e elimina aluno "sumido" na lista.
    """
    if request.method == "POST":
        form = AlunoCreateComTurmaForm(request.POST, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                turma = form.cleaned_data["turma"]
                aluno = form.save()

                Matricula.objects.create(
                    aluno=aluno,
                    turma=turma,
                    data_matricula=timezone.localdate(),
                    situacao=Matricula.Situacao.ATIVA,
                )

            messages.success(request, "Aluno criado e matriculado com sucesso.")
            return redirect("educacao:aluno_detail", pk=aluno.pk)

        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AlunoCreateComTurmaForm(user=request.user)

    return render(request, "educacao/aluno_form.html", {"form": form, "mode": "create"})


@login_required
@require_perm("educacao.manage")
def aluno_update(request, pk: int):
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
