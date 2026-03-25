from __future__ import annotations

from decimal import Decimal
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import require_perm
from apps.core.services_auditoria import registrar_auditoria
from apps.core.services_transparencia import publicar_evento_transparencia
from apps.core.rbac import is_admin, scope_filter_locais_estruturais, scope_filter_secretarias, scope_filter_unidades
from apps.org.models import LocalEstrutural, Municipio, Secretaria, Unidade

from .forms import AlmoxarifadoCadastroForm, AlmoxarifadoMovimentoForm, AlmoxarifadoRequisicaoForm
from .models import AlmoxarifadoCadastro, AlmoxarifadoMovimento, AlmoxarifadoRequisicao


def _resolve_municipio(request, *, require_selected: bool = False):
    user = request.user
    if is_admin(user):
        municipio_id = (request.GET.get("municipio") or request.POST.get("municipio") or "").strip()
        if municipio_id.isdigit():
            return Municipio.objects.filter(pk=int(municipio_id), ativo=True).first()
        if require_selected:
            return None
        return Municipio.objects.filter(ativo=True).order_by("nome").first()

    profile = getattr(user, "profile", None)
    if profile and profile.municipio_id:
        return Municipio.objects.filter(pk=profile.municipio_id, ativo=True).first()
    return None

def _municipios_admin(request):
    if not is_admin(request.user):
        return Municipio.objects.none()
    return Municipio.objects.filter(ativo=True).order_by("nome")

def _q_municipio(municipio: Municipio) -> str:
    return f"?municipio={municipio.pk}"


def _q_scope(request) -> str:
    parts: list[str] = []
    for key in ("secretaria", "unidade", "local"):
        value = (request.GET.get(key) or "").strip()
        if value:
            parts.append(f"{key}={value}")
    return ("&" + "&".join(parts)) if parts else ""

def _to_dec(v) -> Decimal:
    return Decimal(str(v or "0"))

def _aplicar_movimento_estoque(mov: AlmoxarifadoMovimento):
    item = mov.item
    if mov.tipo == AlmoxarifadoMovimento.Tipo.ENTRADA:
        novo_saldo = _to_dec(item.saldo_atual) + _to_dec(mov.quantidade)
        item.valor_medio = _to_dec(mov.valor_unitario or item.valor_medio)
    elif mov.tipo == AlmoxarifadoMovimento.Tipo.SAIDA:
        novo_saldo = _to_dec(item.saldo_atual) - _to_dec(mov.quantidade)
    else:
        novo_saldo = _to_dec(mov.quantidade)
    item.saldo_atual = novo_saldo if novo_saldo > 0 else Decimal("0")
    item.save(update_fields=["saldo_atual", "valor_medio", "atualizado_em"])


def _apply_scope_filters(
    request,
    qs,
    *,
    secretaria_field: str | None,
    unidade_field: str | None,
    setor_field: str | None,
    local_field: str | None,
):
    profile = getattr(request.user, "profile", None)

    if not is_admin(request.user) and profile:
        if secretaria_field and getattr(profile, "secretaria_id", None):
            qs = qs.filter(**{f"{secretaria_field}_id": profile.secretaria_id})
        if unidade_field and getattr(profile, "unidade_id", None):
            qs = qs.filter(**{f"{unidade_field}_id": profile.unidade_id})
        if setor_field and getattr(profile, "setor_id", None):
            qs = qs.filter(**{f"{setor_field}_id": profile.setor_id})
        if local_field and getattr(profile, "local_estrutural_id", None):
            qs = qs.filter(**{f"{local_field}_id": profile.local_estrutural_id})

    secretaria_id = (request.GET.get("secretaria") or "").strip()
    unidade_id = (request.GET.get("unidade") or "").strip()
    setor_id = (request.GET.get("setor") or "").strip()
    local_id = (request.GET.get("local") or "").strip()

    if secretaria_field and secretaria_id.isdigit():
        qs = qs.filter(**{f"{secretaria_field}_id": int(secretaria_id)})
    if unidade_field and unidade_id.isdigit():
        qs = qs.filter(**{f"{unidade_field}_id": int(unidade_id)})
    if setor_field and setor_id.isdigit():
        qs = qs.filter(**{f"{setor_field}_id": int(setor_id)})
    if local_field and local_id.isdigit():
        qs = qs.filter(**{f"{local_field}_id": int(local_id)})

    return qs


def _scope_context(request, municipio: Municipio):
    secretaria_id = (request.GET.get("secretaria") or "").strip()
    unidade_id = (request.GET.get("unidade") or "").strip()
    local_id = (request.GET.get("local") or "").strip()

    secretarias = scope_filter_secretarias(
        request.user,
        Secretaria.objects.filter(municipio=municipio, ativo=True).order_by("nome"),
    )
    unidades = scope_filter_unidades(
        request.user,
        Unidade.objects.filter(secretaria__municipio=municipio, ativo=True).select_related("secretaria").order_by("nome"),
    )
    locais = scope_filter_locais_estruturais(
        request.user,
        LocalEstrutural.objects.filter(municipio=municipio, status=LocalEstrutural.Status.ATIVO)
        .select_related("unidade", "secretaria")
        .order_by("nome"),
    )

    if secretaria_id.isdigit():
        unidades = unidades.filter(secretaria_id=int(secretaria_id))
        locais = locais.filter(secretaria_id=int(secretaria_id))
    if unidade_id.isdigit():
        locais = locais.filter(unidade_id=int(unidade_id))

    return {
        "secretarias": secretarias,
        "unidades": unidades,
        "locais": locais,
        "secretaria_id": secretaria_id,
        "unidade_id": unidade_id,
        "local_id": local_id,
    }


def _parse_date(value: str) -> date | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None
