from __future__ import annotations

from urllib.parse import urlencode

from django.contrib.auth import get_user_model

from apps.core.rbac import get_profile, is_admin
from apps.org.models import Municipio, Secretaria, Setor, Unidade
from .models import UserManagementAudit

User = get_user_model()


def can_manage_users(user) -> bool:
    if is_admin(user):
        return True
    p = get_profile(user)
    return bool(p and p.ativo and p.role in {"MUNICIPAL", "SECRETARIA", "UNIDADE"})


def scope_users_queryset(request):
    qs = User.objects.select_related(
        "profile",
        "profile__municipio",
        "profile__secretaria",
        "profile__unidade",
        "profile__setor",
    ).all().order_by("id")
    if is_admin(request.user):
        return qs

    p = get_profile(request.user)
    if not p or not p.ativo:
        return qs.none()

    if getattr(p, "setor_id", None):
        return qs.filter(profile__setor_id=p.setor_id)

    if getattr(p, "unidade_id", None):
        return qs.filter(profile__unidade_id=p.unidade_id)

    if getattr(p, "secretaria_id", None):
        return qs.filter(profile__secretaria_id=p.secretaria_id)

    if getattr(p, "municipio_id", None):
        return qs.filter(profile__municipio_id=p.municipio_id)

    return qs.none()


def log_user_action(*, actor, target, action: str, details: str = "") -> None:
    UserManagementAudit.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        target=target,
        action=action,
        details=details or "",
    )


def build_filter_scopes(request, *, municipio_id: str, secretaria_id: str, unidade_id: str):
    p = get_profile(request.user)

    municipios_qs = Municipio.objects.filter(ativo=True).order_by("nome")
    secretarias_qs = Secretaria.objects.filter(ativo=True).select_related("municipio").order_by("nome")
    unidades_qs = Unidade.objects.filter(ativo=True).select_related("secretaria", "secretaria__municipio").order_by("nome")
    setores_qs = Setor.objects.filter(ativo=True).select_related("unidade", "unidade__secretaria", "unidade__secretaria__municipio").order_by("nome")

    if not is_admin(request.user) and p:
        if getattr(p, "municipio_id", None):
            municipios_qs = municipios_qs.filter(id=p.municipio_id)
            secretarias_qs = secretarias_qs.filter(municipio_id=p.municipio_id)
            unidades_qs = unidades_qs.filter(secretaria__municipio_id=p.municipio_id)
            setores_qs = setores_qs.filter(unidade__secretaria__municipio_id=p.municipio_id)
        if getattr(p, "secretaria_id", None):
            secretarias_qs = secretarias_qs.filter(id=p.secretaria_id)
            unidades_qs = unidades_qs.filter(secretaria_id=p.secretaria_id)
            setores_qs = setores_qs.filter(unidade__secretaria_id=p.secretaria_id)
        if getattr(p, "unidade_id", None):
            unidades_qs = unidades_qs.filter(id=p.unidade_id)
            setores_qs = setores_qs.filter(unidade_id=p.unidade_id)
        if getattr(p, "setor_id", None):
            setores_qs = setores_qs.filter(id=p.setor_id)

    if municipio_id.isdigit():
        secretarias_qs = secretarias_qs.filter(municipio_id=int(municipio_id))
        unidades_qs = unidades_qs.filter(secretaria__municipio_id=int(municipio_id))
        setores_qs = setores_qs.filter(unidade__secretaria__municipio_id=int(municipio_id))

    if secretaria_id.isdigit():
        unidades_qs = unidades_qs.filter(secretaria_id=int(secretaria_id))
        setores_qs = setores_qs.filter(unidade__secretaria_id=int(secretaria_id))

    if unidade_id.isdigit():
        setores_qs = setores_qs.filter(unidade_id=int(unidade_id))

    return {
        "municipios": list(municipios_qs.values_list("id", "nome")),
        "secretarias": list(secretarias_qs.values_list("id", "nome")),
        "unidades": list(unidades_qs.values_list("id", "nome")),
        "setores": list(setores_qs.values_list("id", "nome")),
    }


def build_querystring(params: dict[str, str | int | None], **updates) -> str:
    data = {}
    for k, v in params.items():
        if v in (None, ""):
            continue
        data[k] = str(v)
    for k, v in updates.items():
        if v in (None, ""):
            data.pop(k, None)
        else:
            data[k] = str(v)
    return urlencode(data)
