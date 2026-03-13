from __future__ import annotations

import json
from typing import Any

from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_http_methods

from apps.core.decorators import require_perm
from apps.core.services_auditoria import registrar_auditoria
from apps.org.models import Address
from apps.org.services.addresses import (
    build_address_query,
    build_directions_url,
    geocode_address,
    normalize_address_payload,
)
from apps.org.services.addresses_access import (
    SUPPORTED_ENTITY_TYPES,
    can_edit_entity_address,
    can_view_coordinates,
    can_view_entity_address,
    get_scoped_entity,
    normalize_entity_type,
)


MUTABLE_FIELDS = {
    "label",
    "cep",
    "logradouro",
    "numero",
    "complemento",
    "bairro",
    "cidade",
    "estado",
    "pais",
    "reference_point",
    "coverage_area",
    "opening_hours",
    "latitude",
    "longitude",
    "is_primary",
    "is_public",
    "is_active",
}


@require_perm("org.view")
@require_http_methods(["GET"])
def address_list(request: HttpRequest):
    entity_type = normalize_entity_type(request.GET.get("entity_type"))
    entity_id = _parse_int(request.GET.get("entity_id"))
    if entity_type not in SUPPORTED_ENTITY_TYPES or entity_id is None:
        return JsonResponse({"ok": False, "error": "entity_type/entity_id_invalid"}, status=400)

    if not can_view_entity_address(request.user, entity_type, entity_id):
        return HttpResponseForbidden("403 — Você não pode visualizar endereços desta entidade.")

    show_coords = can_view_coordinates(request.user, entity_type, entity_id)
    qs = Address.objects.filter(entity_type=entity_type, entity_id=entity_id, is_active=True).order_by("-is_primary", "id")
    return JsonResponse({"ok": True, "results": [_serialize_address(addr, show_coords) for addr in qs]})


@require_perm("org.view")
@require_http_methods(["POST"])
def address_create(request: HttpRequest):
    payload = _parse_payload(request)
    entity_type = normalize_entity_type(payload.get("entity_type"))
    entity_id = _parse_int(payload.get("entity_id"))
    if entity_type not in SUPPORTED_ENTITY_TYPES or entity_id is None:
        return JsonResponse({"ok": False, "error": "entity_type/entity_id_invalid"}, status=400)

    entity = get_scoped_entity(request.user, entity_type, entity_id)
    if entity is None:
        return JsonResponse({"ok": False, "error": "entidade_nao_encontrada_ou_sem_escopo"}, status=404)
    if not can_edit_entity_address(request.user, entity_type, entity_id):
        return HttpResponseForbidden("403 — Você não pode editar endereços desta entidade.")

    data = normalize_address_payload(payload)
    has_active = Address.objects.filter(entity_type=entity_type, entity_id=entity_id, is_active=True).exists()

    address = Address(
        entity_type=entity_type,
        entity_id=entity_id,
        label=data.get("label") or "Principal",
        cep=data.get("cep") or "",
        logradouro=data.get("logradouro") or "",
        numero=data.get("numero") or "",
        complemento=data.get("complemento") or "",
        bairro=data.get("bairro") or "",
        cidade=data.get("cidade") or "",
        estado=data.get("estado") or "",
        pais=data.get("pais") or "BR",
        reference_point=data.get("reference_point") or "",
        coverage_area=data.get("coverage_area") or "",
        opening_hours=data.get("opening_hours") or "",
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        is_primary=bool(data.get("is_primary") or not has_active),
        is_public=bool(data.get("is_public", True)),
        is_active=True,
        created_by=request.user,
        updated_by=request.user,
    )

    if address.latitude is not None and address.longitude is not None:
        address.geocode_provider = Address.GeocodeProvider.MANUAL
        address.geocode_status = Address.GeocodeStatus.MANUAL
    else:
        _apply_geocode(address, force=False)

    try:
        address.save()
    except ValidationError as exc:
        return JsonResponse({"ok": False, "errors": exc.message_dict}, status=400)

    _enforce_primary(address)
    _audit(
        request=request,
        entity=entity,
        event="ADDRESS_CREATED",
        address=address,
        before={},
        after=_serialize_address(address, show_coordinates=True),
    )

    return JsonResponse({"ok": True, "address": _serialize_address(address, can_view_coordinates(request.user, entity_type, entity_id))}, status=201)


@require_perm("org.view")
@require_http_methods(["PUT"])
def address_update(request: HttpRequest, pk: int):
    address = Address.objects.filter(pk=pk, is_active=True).first()
    if not address:
        return JsonResponse({"ok": False, "error": "endereco_nao_encontrado"}, status=404)

    entity = get_scoped_entity(request.user, address.entity_type, address.entity_id)
    if entity is None:
        return JsonResponse({"ok": False, "error": "entidade_nao_encontrada_ou_sem_escopo"}, status=404)
    if not can_edit_entity_address(request.user, address.entity_type, address.entity_id):
        return HttpResponseForbidden("403 — Você não pode editar este endereço.")

    payload = _parse_payload(request)
    data = normalize_address_payload(payload)
    before = _serialize_address(address, show_coordinates=True)

    changed_location_fields = False
    for field in MUTABLE_FIELDS:
        if field not in payload:
            continue
        value = data.get(field)
        if field in {
            "label",
            "cep",
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "estado",
            "pais",
            "reference_point",
            "coverage_area",
            "opening_hours",
        } and getattr(address, field) != value:
            changed_location_fields = True
        setattr(address, field, value)

    if "entity_type" in payload or "entity_id" in payload:
        return JsonResponse({"ok": False, "error": "entity_type/entity_id_sao_imutaveis"}, status=400)

    if address.latitude is not None and address.longitude is not None and (
        "latitude" in payload or "longitude" in payload
    ):
        address.geocode_provider = Address.GeocodeProvider.MANUAL
        address.geocode_status = Address.GeocodeStatus.MANUAL

    force_geocode = _to_bool(payload.get("force_geocode"))
    if force_geocode:
        _apply_geocode(address, force=True)
    elif address.latitude is None and address.longitude is None and changed_location_fields:
        _apply_geocode(address, force=False)

    address.updated_by = request.user

    try:
        address.save()
    except ValidationError as exc:
        return JsonResponse({"ok": False, "errors": exc.message_dict}, status=400)

    _enforce_primary(address)
    after = _serialize_address(address, show_coordinates=True)
    _audit(
        request=request,
        entity=entity,
        event="ADDRESS_UPDATED",
        address=address,
        before=before,
        after=after,
    )

    return JsonResponse({"ok": True, "address": _serialize_address(address, can_view_coordinates(request.user, address.entity_type, address.entity_id))})


@require_perm("org.view")
@require_http_methods(["DELETE"])
def address_delete(request: HttpRequest, pk: int):
    address = Address.objects.filter(pk=pk, is_active=True).first()
    if not address:
        return JsonResponse({"ok": False, "error": "endereco_nao_encontrado"}, status=404)

    entity = get_scoped_entity(request.user, address.entity_type, address.entity_id)
    if entity is None:
        return JsonResponse({"ok": False, "error": "entidade_nao_encontrada_ou_sem_escopo"}, status=404)
    if not can_edit_entity_address(request.user, address.entity_type, address.entity_id):
        return HttpResponseForbidden("403 — Você não pode remover este endereço.")

    before = _serialize_address(address, show_coordinates=True)

    address.is_active = False
    address.is_primary = False
    address.updated_by = request.user
    address.save(update_fields=["is_active", "is_primary", "updated_by", "updated_at"])

    replacement = (
        Address.objects.filter(
            entity_type=address.entity_type,
            entity_id=address.entity_id,
            is_active=True,
        )
        .order_by("id")
        .first()
    )
    if replacement and not replacement.is_primary:
        replacement.is_primary = True
        replacement.save(update_fields=["is_primary", "updated_at"])

    _audit(
        request=request,
        entity=entity,
        event="ADDRESS_DEACTIVATED",
        address=address,
        before=before,
        after={"is_active": False, "is_primary": False},
    )

    return JsonResponse({"ok": True})


@require_perm("org.view")
@require_http_methods(["POST"])
def address_reprocess_geocode(request: HttpRequest, pk: int):
    address = Address.objects.filter(pk=pk, is_active=True).first()
    if not address:
        return JsonResponse({"ok": False, "error": "endereco_nao_encontrado"}, status=404)

    entity = get_scoped_entity(request.user, address.entity_type, address.entity_id)
    if entity is None:
        return JsonResponse({"ok": False, "error": "entidade_nao_encontrada_ou_sem_escopo"}, status=404)
    if not can_edit_entity_address(request.user, address.entity_type, address.entity_id):
        return HttpResponseForbidden("403 — Você não pode reprocessar este endereço.")

    before = _serialize_address(address, show_coordinates=True)
    geo = _apply_geocode(address, force=True)
    address.updated_by = request.user

    try:
        address.save()
    except ValidationError as exc:
        return JsonResponse({"ok": False, "errors": exc.message_dict}, status=400)

    after = _serialize_address(address, show_coordinates=True)
    _audit(
        request=request,
        entity=entity,
        event="ADDRESS_GEOCODE_REPROCESS",
        address=address,
        before=before,
        after=after,
        note=f"provider={geo.get('provider', '')};ok={geo.get('ok', False)}",
    )

    return JsonResponse({"ok": True, "address": _serialize_address(address, can_view_coordinates(request.user, address.entity_type, address.entity_id)), "geocode": geo})


def _serialize_address(address: Address, show_coordinates: bool = False) -> dict[str, Any]:
    query = build_address_query(
        {
            "logradouro": address.logradouro,
            "numero": address.numero,
            "bairro": address.bairro,
            "cidade": address.cidade,
            "estado": address.estado,
            "cep": address.cep,
            "pais": address.pais,
        }
    )
    return {
        "id": address.id,
        "entity_type": address.entity_type,
        "entity_id": address.entity_id,
        "label": address.label,
        "is_primary": address.is_primary,
        "is_public": address.is_public,
        "is_active": address.is_active,
        "cep": address.cep,
        "logradouro": address.logradouro,
        "numero": address.numero,
        "complemento": address.complemento,
        "bairro": address.bairro,
        "cidade": address.cidade,
        "estado": address.estado,
        "pais": address.pais,
        "reference_point": address.reference_point,
        "coverage_area": address.coverage_area,
        "opening_hours": address.opening_hours,
        "formatted_address": address.formatted_address(),
        "address_query": query,
        "latitude": float(address.latitude) if (show_coordinates and address.latitude is not None) else None,
        "longitude": float(address.longitude) if (show_coordinates and address.longitude is not None) else None,
        "geocode_provider": address.geocode_provider,
        "geocode_status": address.geocode_status,
        "maps_url": address.maps_url,
        "directions_url": build_directions_url(address.latitude, address.longitude, query),
    }


def _apply_geocode(address: Address, force: bool = False) -> dict[str, Any]:
    has_coordinates = address.latitude is not None and address.longitude is not None
    if has_coordinates and not force:
        return {
            "ok": True,
            "provider": address.geocode_provider,
            "latitude": address.latitude,
            "longitude": address.longitude,
            "source": "existing",
        }

    result = geocode_address(
        {
            "logradouro": address.logradouro,
            "numero": address.numero,
            "bairro": address.bairro,
            "cidade": address.cidade,
            "estado": address.estado,
            "cep": address.cep,
            "pais": address.pais,
        }
    )

    if result.get("ok"):
        address.latitude = result.get("latitude")
        address.longitude = result.get("longitude")
        address.geocode_provider = str(result.get("provider") or Address.GeocodeProvider.NONE)
        address.geocode_status = Address.GeocodeStatus.OK
    elif not has_coordinates:
        address.geocode_provider = str(result.get("provider") or Address.GeocodeProvider.NONE)
        address.geocode_status = Address.GeocodeStatus.FAILED

    return result


def _enforce_primary(address: Address) -> None:
    if address.is_primary:
        Address.objects.filter(
            entity_type=address.entity_type,
            entity_id=address.entity_id,
            is_active=True,
        ).exclude(pk=address.pk).update(is_primary=False)
        return

    has_primary = Address.objects.filter(
        entity_type=address.entity_type,
        entity_id=address.entity_id,
        is_active=True,
        is_primary=True,
    ).exists()
    if not has_primary:
        address.is_primary = True
        address.save(update_fields=["is_primary", "updated_at"])


def _parse_payload(request: HttpRequest) -> dict[str, Any]:
    if request.content_type and "application/json" in request.content_type:
        try:
            body = request.body.decode("utf-8") if request.body else "{}"
            payload = json.loads(body or "{}")
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    data = {}
    source = request.POST or request.GET
    for key in source.keys():
        data[key] = source.get(key)
    return data


def _parse_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    val = str(value or "").strip().lower()
    return val in {"1", "true", "on", "yes", "sim"}


def _audit(*, request: HttpRequest, entity, event: str, address: Address, before: dict, after: dict, note: str = ""):
    municipio = _entity_municipio(entity)
    if municipio is None:
        return

    registrar_auditoria(
        municipio=municipio,
        modulo="ORG",
        evento=event,
        entidade="Address",
        entidade_id=address.id,
        usuario=request.user,
        antes=before,
        depois=after,
        observacao=note,
    )


def _entity_municipio(entity):
    if hasattr(entity, "municipio"):
        return getattr(entity, "municipio")
    secretaria = getattr(entity, "secretaria", None)
    if secretaria is not None:
        return getattr(secretaria, "municipio", None)
    return None
