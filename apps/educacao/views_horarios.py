from django.contrib.auth.decorators import login_required

from apps.core.decorators import require_perm

from . import views_horarios_core
from . import views_horarios_management


@login_required
@require_perm("educacao.view")
def horario_turma(request, turma_id: int):
    return views_horarios_core.horario_turma_impl(request, turma_id)


@login_required
@require_perm("educacao.view")
def horario_aula_create(request, turma_id: int):
    return views_horarios_core.horario_aula_create_impl(request, turma_id)


@login_required
@require_perm("educacao.view")
def horario_aula_update(request, turma_id: int, pk: int):
    return views_horarios_core.horario_aula_update_impl(request, turma_id, pk)


@login_required
@require_perm("educacao.manage")
def horario_gerar_padrao(request, turma_id: int):
    return views_horarios_management.horario_gerar_padrao_impl(request, turma_id)


@login_required
@require_perm("educacao.manage")
def horario_duplicar(request, turma_id: int):
    return views_horarios_management.horario_duplicar_impl(request, turma_id)


@login_required
@require_perm("educacao.manage")
def horario_duplicar_select(request, turma_id: int):
    return views_horarios_management.horario_duplicar_select_impl(request, turma_id)


@login_required
@require_perm("educacao.manage")
def horario_limpar(request, turma_id: int):
    return views_horarios_management.horario_limpar_impl(request, turma_id)
