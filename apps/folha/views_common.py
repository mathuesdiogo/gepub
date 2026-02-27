from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import require_perm
from apps.core.exports import export_pdf_table
from apps.core.services_auditoria import registrar_auditoria
from apps.core.services_transparencia import publicar_evento_transparencia
from apps.core.rbac import is_admin
from apps.org.models import Municipio

from .forms import FolhaCadastroForm, FolhaCompetenciaForm, FolhaLancamentoForm
from .models import FolhaCadastro, FolhaCompetencia, FolhaIntegracaoFinanceiro, FolhaLancamento


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

def _to_dec(value) -> Decimal:
    return Decimal(str(value or "0"))

def _recompute_competencia(obj: FolhaCompetencia):
    lancamentos = FolhaLancamento.objects.filter(competencia=obj)
    proventos = (
        lancamentos.filter(evento__tipo_evento=FolhaCadastro.TipoEvento.PROVENTO).aggregate(total=Sum("valor_calculado"))["total"]
        or Decimal("0")
    )
    descontos = (
        lancamentos.filter(evento__tipo_evento=FolhaCadastro.TipoEvento.DESCONTO).aggregate(total=Sum("valor_calculado"))["total"]
        or Decimal("0")
    )
    colaboradores = lancamentos.values("servidor_id").distinct().count()
    obj.total_colaboradores = colaboradores
    obj.total_proventos = _to_dec(proventos)
    obj.total_descontos = _to_dec(descontos)
    obj.total_liquido = _to_dec(proventos) - _to_dec(descontos)
