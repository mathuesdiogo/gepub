from django.contrib.auth.decorators import login_required

from apps.core.decorators import require_perm

from . import views_diario_core
from . import views_diario_frequencia


@login_required
@require_perm("educacao.view")
def meus_diarios(request):
    return views_diario_core.meus_diarios_impl(request)


@login_required
@require_perm("educacao.view")
def diario_detail(request, pk: int):
    return views_diario_core.diario_detail_impl(request, pk)


@login_required
@require_perm("educacao.view")
def aula_frequencia(request, pk: int, aula_id: int):
    return views_diario_frequencia.aula_frequencia_impl(request, pk, aula_id)


@login_required
@require_perm("educacao.view")
def aula_create(request, pk: int):
    return views_diario_core.aula_create_impl(request, pk)


@login_required
@require_perm("educacao.view")
def aula_update(request, pk: int, aula_id: int):
    return views_diario_core.aula_update_impl(request, pk, aula_id)


@login_required
@require_perm("educacao.view")
def api_alunos_turma_suggest(request, pk: int):
    return views_diario_frequencia.api_alunos_turma_suggest_impl(request, pk)


@login_required
@require_perm("educacao.view")
def diario_create_for_turma(request, pk: int):
    return views_diario_core.diario_create_for_turma_impl(request, pk)


@login_required
@require_perm("educacao.view")
def diario_turma_entry(request, pk: int):
    return views_diario_core.diario_turma_entry_impl(request, pk)
