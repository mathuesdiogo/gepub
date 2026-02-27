from __future__ import annotations

from decimal import Decimal

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
from apps.core.rbac import is_admin
from apps.org.models import Municipio

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
