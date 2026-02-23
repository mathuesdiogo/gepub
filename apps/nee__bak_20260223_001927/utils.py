from __future__ import annotations

from django.http import Http404

from apps.core.rbac import scope_filter_alunos
from apps.educacao.models import Aluno


def get_scoped_aluno(user, aluno_id: int) -> Aluno:
    qs = scope_filter_alunos(user, Aluno.objects.filter(id=aluno_id))
    aluno = qs.first()
    if not aluno:
        raise Http404("Aluno não encontrado.")
    return aluno
