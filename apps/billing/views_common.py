from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.decorators import require_perm
from apps.core.exports import export_pdf_table
from apps.core.rbac import can, is_admin
from apps.org.models import Municipio

from .forms import (
    AssinaturaAdminForm,
    BonusQuotaForm,
    FiltroAssinaturaForm,
    SimuladorPlanoForm,
    SolicitacaoUpgradeForm,
)
from .models import (
    AssinaturaMunicipio,
    AssinaturaQuotaExtra,
    FaturaMunicipio,
    SolicitacaoUpgrade,
)
from .services import (
    METRICA_LABEL,
    MetricaLimite,
    aprovar_upgrade,
    gerar_fatura_mensal,
    get_assinatura_ativa,
    limite_efetivo_assinatura,
    recalc_uso_municipio,
    recusar_upgrade,
    resolver_municipio_usuario,
    simular_plano,
)


def _resolve_municipio(request, *, require_admin_select: bool = False) -> Municipio | None:
    user = request.user
    if is_admin(user):
        municipio_id = (request.GET.get("municipio") or request.POST.get("municipio") or "").strip()
        if municipio_id.isdigit():
            return Municipio.objects.filter(pk=int(municipio_id)).first()
        if require_admin_select:
            return None
        return Municipio.objects.order_by("nome").first()

    return resolver_municipio_usuario(user)

def _metricas_para_tela(assinatura: AssinaturaMunicipio, uso):
    metricas = []
    mapa = [
        (MetricaLimite.SECRETARIAS, uso.secretarias_ativas),
        (MetricaLimite.USUARIOS, uso.usuarios_ativos),
        (MetricaLimite.ALUNOS, uso.alunos_ativos),
        (MetricaLimite.ATENDIMENTOS, uso.atendimentos_ano),
    ]
    for metrica, usado in mapa:
        limite = limite_efetivo_assinatura(assinatura, metrica)
        percentual = None
        classe = "ok"
        disponivel = None
        if limite is not None and limite > 0:
            percentual = min(100, int((int(usado) * 100) / int(limite)))
            disponivel = max(0, int(limite) - int(usado))
            if percentual >= 90:
                classe = "danger"
            elif percentual >= 70:
                classe = "warning"
        metricas.append(
            {
                "codigo": metrica,
                "label": METRICA_LABEL.get(metrica, metrica).capitalize(),
                "usado": int(usado),
                "limite": limite,
                "disponivel": disponivel,
                "percentual": percentual,
                "classe": classe,
            }
        )
    return metricas
