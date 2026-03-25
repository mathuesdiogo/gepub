from __future__ import annotations

from collections import Counter
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from apps.accounts.models import Profile
from apps.accounts.views_users_common import scope_users_queryset
from apps.core.rbac import can, get_profile, is_admin
from apps.org.models import Address, Secretaria, Setor, Unidade

DELETE_CONFIRM_TEXT = "REMOVER"


def _can_manage_secretarias(user) -> bool:
    return bool(is_admin(user) or can(user, "org.manage_secretaria"))


def _can_manage_unidades(user) -> bool:
    return bool(is_admin(user) or can(user, "org.manage_unidade"))


def _can_manage_usuarios(user) -> bool:
    return bool(is_admin(user) or can(user, "accounts.manage_users"))


def _can_open_exclusoes_hub(user) -> bool:
    return bool(
        _can_manage_secretarias(user)
        or _can_manage_unidades(user)
        or _can_manage_usuarios(user)
    )


def _safe_next(request: HttpRequest, fallback: str) -> str:
    next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}):
        return next_url
    return fallback


def _scope_secretarias_queryset(user):
    qs = Secretaria.objects.select_related("municipio").all()
    if is_admin(user):
        return qs

    profile = get_profile(user)
    if not profile or not getattr(profile, "ativo", True):
        return qs.none()

    if getattr(profile, "setor_id", None):
        secretaria_id = (
            Setor.objects.filter(pk=profile.setor_id)
            .values_list("unidade__secretaria_id", flat=True)
            .first()
        )
        return qs.filter(pk=secretaria_id) if secretaria_id else qs.none()

    if getattr(profile, "unidade_id", None):
        secretaria_id = (
            Unidade.objects.filter(pk=profile.unidade_id)
            .values_list("secretaria_id", flat=True)
            .first()
        )
        return qs.filter(pk=secretaria_id) if secretaria_id else qs.none()

    if getattr(profile, "secretaria_id", None):
        return qs.filter(pk=profile.secretaria_id)

    if getattr(profile, "municipio_id", None):
        return qs.filter(municipio_id=profile.municipio_id)

    return qs.none()


def _scope_unidades_queryset(user):
    qs = Unidade.objects.select_related("secretaria__municipio").all()
    if is_admin(user):
        return qs

    profile = get_profile(user)
    if not profile or not getattr(profile, "ativo", True):
        return qs.none()

    if getattr(profile, "setor_id", None):
        unidade_id = (
            Setor.objects.filter(pk=profile.setor_id)
            .values_list("unidade_id", flat=True)
            .first()
        )
        return qs.filter(pk=unidade_id) if unidade_id else qs.none()

    if getattr(profile, "unidade_id", None):
        return qs.filter(pk=profile.unidade_id)

    if getattr(profile, "secretaria_id", None):
        return qs.filter(secretaria_id=profile.secretaria_id)

    if getattr(profile, "municipio_id", None):
        return qs.filter(secretaria__municipio_id=profile.municipio_id)

    return qs.none()


def _user_delete_guard(actor, target, target_profile: Profile | None) -> tuple[bool, str]:
    if target.pk == actor.pk:
        return False, "Não é permitido remover o próprio usuário logado."
    if target.is_superuser:
        return False, "Superusuário não pode ser removido por esta tela."
    if target.is_staff and not is_admin(actor):
        return False, "Usuário da equipe técnica só pode ser removido por administrador."
    if (
        target_profile
        and getattr(target_profile, "role", "") == Profile.Role.ADMIN
        and not is_admin(actor)
    ):
        return False, "Somente administrador pode remover usuário com perfil ADMIN."
    return True, ""


def _format_scope_label(profile: Profile | None) -> str:
    if not profile:
        return "Sem perfil"
    if profile.setor:
        return f"Setor: {profile.setor.nome}"
    if profile.unidade:
        return f"Unidade: {profile.unidade.nome}"
    if profile.secretaria:
        return f"Secretaria: {profile.secretaria.nome}"
    if profile.municipio:
        return f"Município: {profile.municipio.nome}/{profile.municipio.uf}"
    return "Sem escopo"


def _format_protected_error(exc: ProtectedError) -> str:
    counters: Counter[str] = Counter()
    for instance in list(exc.protected_objects):
        meta = getattr(instance, "_meta", None)
        label = ""
        if meta is not None:
            label = str(getattr(meta, "verbose_name_plural", "") or getattr(meta, "verbose_name", "")).strip()
        if not label:
            label = instance.__class__.__name__
        counters[label] += 1

    if not counters:
        return "registros vinculados"

    parts = [f"{label} ({qty})" for label, qty in counters.most_common(6)]
    suffix = "..." if len(counters) > 6 else ""
    return ", ".join(parts) + suffix


def _build_secretaria_delete_payload(request: HttpRequest, pk: int) -> dict[str, Any]:
    if not _can_manage_secretarias(request.user):
        raise PermissionError("Sem permissão para remover secretarias.")

    obj = get_object_or_404(_scope_secretarias_queryset(request.user), pk=pk)
    deps = {
        "unidades": Unidade.objects.filter(secretaria_id=obj.pk).count(),
        "setores": Setor.objects.filter(unidade__secretaria_id=obj.pk).count(),
        "perfis": Profile.objects.filter(secretaria_id=obj.pk).count(),
        "enderecos": Address.objects.filter(
            entity_type=Address.EntityType.SECRETARIA,
            entity_id=obj.pk,
            is_active=True,
        ).count(),
    }
    blockers = []
    if deps["unidades"] > 0:
        blockers.append("Há unidades vinculadas.")
    if deps["setores"] > 0:
        blockers.append("Há setores vinculados.")
    if deps["perfis"] > 0:
        blockers.append("Há usuários/perfis vinculados.")

    return {
        "entity_type": "secretaria",
        "entity_label": "Secretaria",
        "title": obj.nome,
        "subtitle": f"{obj.municipio.nome}/{obj.municipio.uf}",
        "object": obj,
        "dependencies": deps,
        "blockers": blockers,
        "can_delete": len(blockers) == 0,
        "success_message": f"Secretaria '{obj.nome}' removida com sucesso.",
    }


def _build_unidade_delete_payload(request: HttpRequest, pk: int) -> dict[str, Any]:
    if not _can_manage_unidades(request.user):
        raise PermissionError("Sem permissão para remover unidades.")

    obj = get_object_or_404(_scope_unidades_queryset(request.user), pk=pk)
    deps = {
        "setores": Setor.objects.filter(unidade_id=obj.pk).count(),
        "perfis": Profile.objects.filter(unidade_id=obj.pk).count(),
        "enderecos": Address.objects.filter(
            entity_type=Address.EntityType.UNIDADE,
            entity_id=obj.pk,
            is_active=True,
        ).count(),
    }
    blockers = []
    if deps["setores"] > 0:
        blockers.append("Há setores vinculados.")
    if deps["perfis"] > 0:
        blockers.append("Há usuários/perfis vinculados.")

    secretaria_nome = obj.secretaria.nome if obj.secretaria else "Sem secretaria"
    return {
        "entity_type": "unidade",
        "entity_label": "Unidade",
        "title": obj.nome or f"Unidade #{obj.pk}",
        "subtitle": secretaria_nome,
        "object": obj,
        "dependencies": deps,
        "blockers": blockers,
        "can_delete": len(blockers) == 0,
        "success_message": f"Unidade '{obj.nome or obj.pk}' removida com sucesso.",
    }


def _build_usuario_delete_payload(request: HttpRequest, pk: int) -> dict[str, Any]:
    if not _can_manage_usuarios(request.user):
        raise PermissionError("Sem permissão para remover usuários.")

    obj = get_object_or_404(scope_users_queryset(request), pk=pk)
    profile = getattr(obj, "profile", None)
    can_delete, reason = _user_delete_guard(request.user, obj, profile)
    blockers = [reason] if reason else []
    role_label = profile.get_role_display() if profile and getattr(profile, "role", "") else "Sem função"
    return {
        "entity_type": "usuario",
        "entity_label": "Usuário",
        "title": obj.get_full_name() or obj.username,
        "subtitle": f"{role_label} • {_format_scope_label(profile)}",
        "object": obj,
        "dependencies": {},
        "blockers": blockers,
        "can_delete": can_delete,
        "success_message": f"Usuário '{obj.get_full_name() or obj.username}' removido com sucesso.",
    }


def _build_delete_payload(request: HttpRequest, entity_type: str, pk: int) -> dict[str, Any]:
    entity_key = (entity_type or "").strip().lower()
    if entity_key == "secretaria":
        return _build_secretaria_delete_payload(request, pk)
    if entity_key == "unidade":
        return _build_unidade_delete_payload(request, pk)
    if entity_key == "usuario":
        return _build_usuario_delete_payload(request, pk)
    raise Http404("Tipo de entidade não suportado para exclusão.")


@login_required
@require_http_methods(["GET"])
def sistema_exclusoes(request: HttpRequest) -> HttpResponse:
    if not _can_open_exclusoes_hub(request.user):
        return HttpResponseForbidden("403 — Você não tem permissão para acessar a central de exclusões.")

    q = (request.GET.get("q") or "").strip()

    can_secretarias = _can_manage_secretarias(request.user)
    can_unidades = _can_manage_unidades(request.user)
    can_usuarios = _can_manage_usuarios(request.user)

    secretarias_rows: list[dict[str, Any]] = []
    unidades_rows: list[dict[str, Any]] = []
    usuarios_rows: list[dict[str, Any]] = []

    if can_secretarias:
        secretarias_qs = _scope_secretarias_queryset(request.user)
        if q:
            secretarias_qs = secretarias_qs.filter(
                Q(nome__icontains=q)
                | Q(sigla__icontains=q)
                | Q(municipio__nome__icontains=q)
            )
        secretarias_qs = (
            secretarias_qs.annotate(
                qtd_unidades=Count("unidades", distinct=True),
                qtd_setores=Count("unidades__setores", distinct=True),
                qtd_perfis=Count("profiles", distinct=True),
            )
            .order_by("nome")[:40]
        )
        secretaria_ids = [obj.id for obj in secretarias_qs]
        secretaria_address_map = dict(
            Address.objects.filter(
                entity_type=Address.EntityType.SECRETARIA,
                entity_id__in=secretaria_ids,
                is_active=True,
            )
            .values("entity_id")
            .annotate(total=Count("id"))
            .values_list("entity_id", "total")
        )
        for item in secretarias_qs:
            blocked = bool(item.qtd_unidades or item.qtd_setores or item.qtd_perfis)
            secretarias_rows.append(
                {
                    "id": item.pk,
                    "nome": item.nome,
                    "sigla": item.sigla or "—",
                    "municipio": f"{item.municipio.nome}/{item.municipio.uf}",
                    "qtd_unidades": int(item.qtd_unidades or 0),
                    "qtd_setores": int(item.qtd_setores or 0),
                    "qtd_perfis": int(item.qtd_perfis or 0),
                    "qtd_enderecos": int(secretaria_address_map.get(item.pk, 0)),
                    "can_delete": not blocked,
                    "confirm_url": reverse("core:sistema_exclusoes_confirmar", args=["secretaria", item.pk]),
                }
            )

    if can_unidades:
        unidades_qs = _scope_unidades_queryset(request.user)
        if q:
            unidades_qs = unidades_qs.filter(
                Q(nome__icontains=q)
                | Q(secretaria__nome__icontains=q)
                | Q(secretaria__municipio__nome__icontains=q)
            )
        unidades_qs = (
            unidades_qs.annotate(
                qtd_setores=Count("setores", distinct=True),
                qtd_perfis=Count("profiles", distinct=True),
            )
            .order_by("nome")[:40]
        )
        unidade_ids = [obj.id for obj in unidades_qs]
        unidade_address_map = dict(
            Address.objects.filter(
                entity_type=Address.EntityType.UNIDADE,
                entity_id__in=unidade_ids,
                is_active=True,
            )
            .values("entity_id")
            .annotate(total=Count("id"))
            .values_list("entity_id", "total")
        )
        for item in unidades_qs:
            blocked = bool(item.qtd_setores or item.qtd_perfis)
            municipio_label = "—"
            if item.secretaria and item.secretaria.municipio:
                municipio_label = f"{item.secretaria.municipio.nome}/{item.secretaria.municipio.uf}"
            unidades_rows.append(
                {
                    "id": item.pk,
                    "nome": item.nome or "—",
                    "secretaria": item.secretaria.nome if item.secretaria else "—",
                    "municipio": municipio_label,
                    "qtd_setores": int(item.qtd_setores or 0),
                    "qtd_perfis": int(item.qtd_perfis or 0),
                    "qtd_enderecos": int(unidade_address_map.get(item.pk, 0)),
                    "can_delete": not blocked,
                    "confirm_url": reverse("core:sistema_exclusoes_confirmar", args=["unidade", item.pk]),
                }
            )

    if can_usuarios:
        usuarios_qs = scope_users_queryset(request).select_related(
            "profile",
            "profile__municipio",
            "profile__secretaria",
            "profile__unidade",
            "profile__setor",
        )
        if q:
            usuarios_qs = usuarios_qs.filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(username__icontains=q)
                | Q(email__icontains=q)
                | Q(profile__codigo_acesso__icontains=q)
            )
        usuarios_qs = usuarios_qs.order_by("first_name", "last_name", "username")[:40]
        for item in usuarios_qs:
            profile = getattr(item, "profile", None)
            role_label = profile.get_role_display() if profile and getattr(profile, "role", "") else "Sem função"
            scope_label = _format_scope_label(profile)
            can_delete, reason = _user_delete_guard(request.user, item, profile)
            usuarios_rows.append(
                {
                    "id": item.pk,
                    "nome": item.get_full_name() or item.username,
                    "username": item.username,
                    "email": item.email or "—",
                    "role": role_label,
                    "scope": scope_label,
                    "status": (
                        "Ativo"
                        if (profile and profile.ativo and not profile.bloqueado)
                        else ("Bloqueado" if (profile and profile.bloqueado) else "Inativo")
                    ),
                    "can_delete": can_delete,
                    "block_reason": reason,
                    "confirm_url": reverse("core:sistema_exclusoes_confirmar", args=["usuario", item.pk]),
                }
            )

    context = {
        "title": "Central de Exclusões",
        "subtitle": "Exclusão controlada de secretarias, unidades e usuários.",
        "actions": [
            {"label": "Voltar", "url": reverse("core:dashboard"), "icon": "fa-solid fa-arrow-left", "variant": "gp-button--ghost"},
        ],
        "q": q,
        "can_manage_secretarias": can_secretarias,
        "can_manage_unidades": can_unidades,
        "can_manage_usuarios": can_usuarios,
        "has_any_section": any([can_secretarias, can_unidades, can_usuarios]),
        "secretarias_rows": secretarias_rows,
        "unidades_rows": unidades_rows,
        "usuarios_rows": usuarios_rows,
    }
    return render(request, "core/sistema_exclusoes.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def sistema_exclusoes_confirmar(request: HttpRequest, entity_type: str, pk: int) -> HttpResponse:
    if not _can_open_exclusoes_hub(request.user):
        return HttpResponseForbidden("403 — Você não tem permissão para acessar a central de exclusões.")

    try:
        payload = _build_delete_payload(request, entity_type, pk)
    except PermissionError as exc:
        return HttpResponseForbidden(f"403 — {exc}")

    back_url = _safe_next(request, reverse("core:sistema_exclusoes"))

    if request.method == "POST":
        confirm_text = (request.POST.get("confirm_text") or "").strip().upper()
        if confirm_text != DELETE_CONFIRM_TEXT:
            messages.error(request, f"Confirmação inválida. Digite exatamente '{DELETE_CONFIRM_TEXT}'.")
            return redirect(back_url)

        if not payload["can_delete"]:
            blockers = payload.get("blockers") or []
            msg = "Não foi possível remover: há vínculos ativos."
            if blockers:
                msg = f"{msg} {' '.join(blockers)}"
            messages.error(request, msg)
            return redirect(back_url)

        target = payload["object"]
        target_label = payload["entity_label"]
        try:
            with transaction.atomic():
                if payload["entity_type"] == "secretaria":
                    Address.objects.filter(
                        entity_type=Address.EntityType.SECRETARIA,
                        entity_id=target.pk,
                    ).delete()
                    target.delete()
                elif payload["entity_type"] == "unidade":
                    Address.objects.filter(
                        entity_type=Address.EntityType.UNIDADE,
                        entity_id=target.pk,
                    ).delete()
                    target.delete()
                elif payload["entity_type"] == "usuario":
                    target.delete()
                else:
                    raise Http404("Tipo de entidade inválido.")
        except ProtectedError as exc:
            details = _format_protected_error(exc)
            messages.error(
                request,
                f"Não foi possível remover {target_label.lower()}: existem vínculos em {details}.",
            )
            return redirect(back_url)
        except Exception:
            messages.error(
                request,
                f"Falha ao remover {target_label.lower()}. Tente novamente ou revise os vínculos.",
            )
            return redirect(back_url)

        messages.success(request, payload["success_message"])
        return redirect(back_url)

    context = {
        "title": f"Confirmar remoção de {payload['entity_label'].lower()}",
        "subtitle": "Esta ação não pode ser desfeita.",
        "actions": [
            {"label": "Voltar", "url": back_url, "icon": "fa-solid fa-arrow-left", "variant": "gp-button--ghost"},
        ],
        "entity_label": payload["entity_label"],
        "entity_title": payload["title"],
        "entity_subtitle": payload["subtitle"],
        "dependencies": payload.get("dependencies", {}),
        "blockers": payload.get("blockers", []),
        "can_delete": payload["can_delete"],
        "confirm_text": DELETE_CONFIRM_TEXT,
        "next_url": back_url,
    }
    return render(request, "core/sistema_exclusoes_confirmar.html", context)
