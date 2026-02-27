from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import render

from apps.core.decorators import require_perm
from apps.core.rbac import (
    can,
    scope_filter_alunos,
    scope_filter_matriculas,
    scope_filter_turmas,
    scope_filter_unidades,
)
from apps.org.models import Unidade

from .models import Aluno, Matricula, Turma
from . import views_alunos_crud, views_turmas_crud


@login_required
@require_perm("educacao.view")
def index(request):
    user = request.user
    cache_key = f"edu_dashboard_{user.id}"

    data = cache.get(cache_key)

    if data is None:
        unidades_total = scope_filter_unidades(user, Unidade.objects.all()).count()
        turmas_total = scope_filter_turmas(user, Turma.objects.all()).count()
        alunos_total = scope_filter_alunos(user, Aluno.objects.all()).count()
        matriculas_total = scope_filter_matriculas(user, Matricula.objects.all()).count()

        data = {
            "unidades_total": unidades_total,
            "turmas_total": turmas_total,
            "alunos_total": alunos_total,
            "matriculas_total": matriculas_total,
        }

        cache.set(cache_key, data, 300)

    data["can_edu_manage"] = can(user, "educacao.manage")
    data["can_nee_view"] = can(user, "nee.view")

    return render(request, "educacao/index.html", data)


@login_required
@require_perm("educacao.view")
def turma_list(request):
    return views_turmas_crud.turma_list(request)


@login_required
@require_perm("educacao.view")
def turma_detail(request, pk: int):
    return views_turmas_crud.turma_detail(request, pk)


@login_required
@require_perm("educacao.manage")
def turma_create(request):
    return views_turmas_crud.turma_create(request)


@login_required
@require_perm("educacao.manage")
def turma_update(request, pk: int):
    return views_turmas_crud.turma_update(request, pk)


@login_required
@require_perm("educacao.view")
def aluno_list(request):
    return views_alunos_crud.aluno_list(request)


@login_required
@require_perm("educacao.view")
def aluno_detail(request, pk: int):
    return views_alunos_crud.aluno_detail(request, pk)


@login_required
@require_perm("educacao.manage")
def aluno_create(request):
    return views_alunos_crud.aluno_create(request)


@login_required
@require_perm("educacao.manage")
def aluno_update(request, pk: int):
    return views_alunos_crud.aluno_update(request, pk)
