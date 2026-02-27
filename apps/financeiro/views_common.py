from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import can, is_admin
from apps.org.models import Municipio

from .forms import (
    DespEmpenhoForm,
    DespLiquidacaoForm,
    DespPagamentoForm,
    DespPagamentoRestoForm,
    DespRestosPagarForm,
    FinanceiroContaBancariaForm,
    FinanceiroExercicioForm,
    FinanceiroUnidadeGestoraForm,
    OrcCreditoAdicionalForm,
    OrcDotacaoForm,
    OrcFonteRecursoForm,
    RecConciliacaoAjusteForm,
    RecArrecadacaoForm,
    TesExtratoImportacaoUploadForm,
)
from .models import (
    DespEmpenho,
    DespLiquidacao,
    DespPagamento,
    DespRestosPagar,
    FinanceiroContaBancaria,
    FinanceiroExercicio,
    FinanceiroLogEvento,
    FinanceiroUnidadeGestora,
    OrcCreditoAdicional,
    OrcDotacao,
    OrcFonteRecurso,
    RecConciliacaoItem,
    RecArrecadacao,
    TesExtratoImportacao,
    TesExtratoItem,
)
from .services import (
    desfazer_conciliacao,
    executar_conciliacao_automatica,
    importar_extrato_bancario,
    marcar_item_como_ajuste,
    registrar_arrecadacao,
    registrar_credito_adicional,
    registrar_empenho,
    registrar_liquidacao,
    registrar_pagamento,
    registrar_pagamento_resto,
    registrar_resto_pagar,
)


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

def _selected_exercicio(request, municipio):
    exercicio_id = (request.GET.get("exercicio") or "").strip()
    qs = FinanceiroExercicio.objects.filter(municipio=municipio)
    if exercicio_id.isdigit():
        return qs.filter(pk=int(exercicio_id)).first()
    return qs.order_by("-ano").first()
