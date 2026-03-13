from __future__ import annotations

from apps.core.rbac import (
    can,
    get_profile,
    is_admin,
    role_scope_base,
    scope_filter_secretarias,
    scope_filter_unidades,
)
from apps.org.models import Address, Secretaria, Unidade


SUPPORTED_ENTITY_TYPES = {
    Address.EntityType.SECRETARIA,
    Address.EntityType.UNIDADE,
}


def normalize_entity_type(raw: str | None) -> str:
    return (raw or "").strip().upper()


def get_scoped_entity(user, entity_type: str, entity_id: int):
    et = normalize_entity_type(entity_type)
    if et == Address.EntityType.SECRETARIA:
        qs = scope_filter_secretarias(user, Secretaria.objects.select_related("municipio"))
        return qs.filter(pk=entity_id).first()
    if et == Address.EntityType.UNIDADE:
        qs = scope_filter_unidades(user, Unidade.objects.select_related("secretaria__municipio"))
        return qs.filter(pk=entity_id).first()
    return None


def can_view_entity_address(user, entity_type: str, entity_id: int) -> bool:
    return get_scoped_entity(user, entity_type, entity_id) is not None


def can_edit_entity_address(user, entity_type: str, entity_id: int) -> bool:
    entity = get_scoped_entity(user, entity_type, entity_id)
    if not entity:
        return False

    if is_admin(user):
        return True

    et = normalize_entity_type(entity_type)
    if et == Address.EntityType.SECRETARIA:
        return can(user, "org.manage_secretaria")

    if et == Address.EntityType.UNIDADE:
        if can(user, "org.manage_unidade"):
            return True

        profile = get_profile(user)
        base_scope = role_scope_base(getattr(profile, "role", None) if profile else None)
        return bool(base_scope == "UNIDADE" and getattr(profile, "unidade_id", None) == entity.id)

    return False


def can_view_coordinates(user, entity_type: str, entity_id: int) -> bool:
    if is_admin(user):
        return True
    return can_edit_entity_address(user, entity_type, entity_id)
