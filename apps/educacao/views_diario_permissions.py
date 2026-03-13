from apps.core.rbac import is_professor_profile_role, scope_filter_turmas
from .models import Turma


def is_professor(user) -> bool:
    return is_professor_profile_role(getattr(getattr(user, "profile", None), "role", None))


def can_edit_diario(user, diario) -> bool:
    return is_professor(user) and diario.professor_id == user.id


def can_view_diario(user, diario) -> bool:
    if can_edit_diario(user, diario):
        return True
    turmas_scope = scope_filter_turmas(user, Turma.objects.all()).values_list("id", flat=True)
    return diario.turma_id in set(turmas_scope)
