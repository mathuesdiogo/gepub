from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.decorators import require_perm
from apps.core.rbac import is_admin
from apps.core.services_auditoria import registrar_auditoria
from apps.core.services_transparencia import publicar_evento_transparencia
from apps.financeiro.models import DespLiquidacao
from apps.financeiro.services import registrar_liquidacao
from apps.org.models import Municipio

from .forms import AditivoContratoForm, ContratoAdministrativoForm, MedicaoContratoForm
from .models import ContratoAdministrativo, MedicaoContrato


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


@login_required
@require_perm("contratos.view")
def index(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    return redirect(reverse("contratos:list") + f"?municipio={municipio.pk}")


@login_required
@require_perm("contratos.view")
def contrato_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()

    qs = ContratoAdministrativo.objects.filter(municipio=municipio).select_related("empenho", "requisicao_compra")
    if q:
        qs = qs.filter(Q(numero__icontains=q) | Q(objeto__icontains=q) | Q(fornecedor_nome__icontains=q))
    if status:
        qs = qs.filter(status=status)

    return render(
        request,
        "contratos/list.html",
        {
            "title": "Contratos e Aditivos",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-vigencia_inicio", "-id"),
            "q": q,
            "status": status,
            "status_choices": ContratoAdministrativo.Status.choices,
            "actions": [
                {
                    "label": "Novo contrato",
                    "url": reverse("contratos:create") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Compras",
                    "url": reverse("compras:requisicao_list") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("contratos.manage")
def contrato_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um municipio para criar contrato.")
        return redirect("contratos:list")

    form = ContratoAdministrativoForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user

        if obj.requisicao_compra_id and not obj.empenho_id and obj.requisicao_compra.empenho_id:
            obj.empenho_id = obj.requisicao_compra.empenho_id
        if not obj.objeto and obj.requisicao_compra_id:
            obj.objeto = obj.requisicao_compra.objeto

        obj.save()
        registrar_auditoria(
            municipio=municipio,
            modulo="CONTRATOS",
            evento="CONTRATO_CRIADO",
            entidade="ContratoAdministrativo",
            entidade_id=obj.pk,
            usuario=request.user,
            depois={
                "numero": obj.numero,
                "status": obj.status,
                "valor_total": str(obj.valor_total),
                "vigencia_fim": str(obj.vigencia_fim),
            },
        )
        publicar_evento_transparencia(
            municipio=municipio,
            modulo="CONTRATOS",
            tipo_evento="CONTRATO_CRIADO",
            titulo=f"Contrato {obj.numero} registrado",
            descricao=obj.objeto,
            referencia=obj.numero,
            valor=obj.valor_total,
            dados={
                "status": obj.status,
                "fornecedor": obj.fornecedor_nome,
                "empenho_id": obj.empenho_id,
            },
        )
        messages.success(request, "Contrato criado com sucesso.")
        return redirect(reverse("contratos:detail", args=[obj.pk]) + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo contrato",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("contratos:list") + f"?municipio={municipio.pk}",
            "submit_label": "Salvar contrato",
        },
    )


@login_required
@require_perm("contratos.view")
def contrato_detail(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    obj = get_object_or_404(
        ContratoAdministrativo.objects.select_related("processo_licitatorio", "requisicao_compra", "empenho"),
        pk=pk,
        municipio=municipio,
    )

    fields = [
        {"label": "Numero", "value": obj.numero},
        {"label": "Objeto", "value": obj.objeto},
        {"label": "Fornecedor", "value": obj.fornecedor_nome},
        {"label": "Documento fornecedor", "value": obj.fornecedor_documento or "-"},
        {"label": "Fiscal", "value": obj.fiscal_nome or "-"},
        {"label": "Processo licitatorio", "value": obj.processo_licitatorio or "-"},
        {"label": "Requisicao origem", "value": obj.requisicao_compra or "-"},
        {"label": "Empenho vinculado", "value": obj.empenho or "-"},
    ]
    pills = [
        {"label": "Status", "value": obj.get_status_display()},
        {"label": "Valor total", "value": obj.valor_total},
        {"label": "Inicio", "value": obj.vigencia_inicio},
        {"label": "Fim", "value": obj.vigencia_fim},
    ]

    return render(
        request,
        "contratos/detail.html",
        {
            "title": f"Contrato {obj.numero}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [
                {
                    "label": "Novo aditivo",
                    "url": reverse("contratos:aditivo_create", args=[obj.pk]) + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-file-circle-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Nova medicao",
                    "url": reverse("contratos:medicao_create", args=[obj.pk]) + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-ruler-combined",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Voltar",
                    "url": reverse("contratos:list") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
            "obj": obj,
            "fields": fields,
            "pills": pills,
            "aditivos": obj.aditivos.order_by("-data_ato", "-id"),
            "medicoes": obj.medicoes.order_by("-data_medicao", "-id"),
            "municipio": municipio,
        },
    )


@login_required
@require_perm("contratos.manage")
def aditivo_create(request, contrato_pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    contrato = get_object_or_404(ContratoAdministrativo, pk=contrato_pk, municipio=municipio)
    form = AditivoContratoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        aditivo = form.save(commit=False)
        aditivo.contrato = contrato
        aditivo.save()

        valor_antes = contrato.valor_total
        vigencia_antes = contrato.vigencia_fim
        if aditivo.tipo == aditivo.Tipo.PRAZO and aditivo.nova_vigencia_fim:
            contrato.vigencia_fim = aditivo.nova_vigencia_fim
            contrato.save(update_fields=["vigencia_fim", "atualizado_em"])
        elif aditivo.tipo == aditivo.Tipo.VALOR and aditivo.valor_aditivo:
            contrato.valor_total = (contrato.valor_total or Decimal("0.00")) + aditivo.valor_aditivo
            contrato.save(update_fields=["valor_total", "atualizado_em"])

        registrar_auditoria(
            municipio=municipio,
            modulo="CONTRATOS",
            evento="ADITIVO_REGISTRADO",
            entidade="AditivoContrato",
            entidade_id=aditivo.pk,
            usuario=request.user,
            antes={
                "contrato_valor_total": str(valor_antes),
                "contrato_vigencia_fim": str(vigencia_antes),
            },
            depois={
                "numero": aditivo.numero,
                "tipo": aditivo.tipo,
                "valor_aditivo": str(aditivo.valor_aditivo),
                "contrato_valor_total": str(contrato.valor_total),
                "contrato_vigencia_fim": str(contrato.vigencia_fim),
            },
        )
        publicar_evento_transparencia(
            municipio=municipio,
            modulo="CONTRATOS",
            tipo_evento="ADITIVO_REGISTRADO",
            titulo=f"Aditivo {aditivo.numero} do contrato {contrato.numero}",
            descricao=f"Tipo: {aditivo.get_tipo_display()}",
            referencia=contrato.numero,
            valor=aditivo.valor_aditivo if aditivo.valor_aditivo and aditivo.valor_aditivo > 0 else None,
            dados={"tipo": aditivo.tipo, "nova_vigencia_fim": str(aditivo.nova_vigencia_fim or "")},
        )

        messages.success(request, "Aditivo registrado com sucesso.")
        return redirect(reverse("contratos:detail", args=[contrato.pk]) + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Novo aditivo - {contrato.numero}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("contratos:detail", args=[contrato.pk]) + f"?municipio={municipio.pk}",
            "submit_label": "Salvar aditivo",
        },
    )


@login_required
@require_perm("contratos.manage")
def medicao_create(request, contrato_pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    contrato = get_object_or_404(ContratoAdministrativo, pk=contrato_pk, municipio=municipio)
    form = MedicaoContratoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        medicao = form.save(commit=False)
        medicao.contrato = contrato
        medicao.criado_por = request.user
        medicao.save()
        registrar_auditoria(
            municipio=municipio,
            modulo="CONTRATOS",
            evento="MEDICAO_CRIADA",
            entidade="MedicaoContrato",
            entidade_id=medicao.pk,
            usuario=request.user,
            depois={
                "contrato": contrato.numero,
                "numero": medicao.numero,
                "status": medicao.status,
                "valor_medido": str(medicao.valor_medido),
                "competencia": medicao.competencia,
            },
        )
        publicar_evento_transparencia(
            municipio=municipio,
            modulo="CONTRATOS",
            tipo_evento="MEDICAO_CRIADA",
            titulo=f"Medicao {medicao.numero} registrada",
            descricao=f"Contrato: {contrato.numero}",
            referencia=contrato.numero,
            valor=medicao.valor_medido,
            dados={"status": medicao.status, "competencia": medicao.competencia},
        )
        messages.success(request, "Medicao cadastrada com sucesso.")
        return redirect(reverse("contratos:detail", args=[contrato.pk]) + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Nova medicao - {contrato.numero}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("contratos:detail", args=[contrato.pk]) + f"?municipio={municipio.pk}",
            "submit_label": "Salvar medicao",
        },
    )


@login_required
@require_perm("contratos.manage")
def medicao_atestar(request, medicao_pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    medicao = get_object_or_404(MedicaoContrato.objects.select_related("contrato"), pk=medicao_pk)
    if medicao.contrato.municipio_id != municipio.id:
        return redirect("core:dashboard")

    status_antes = medicao.status
    medicao.status = MedicaoContrato.Status.ATESTADA
    medicao.atestado_por = request.user
    medicao.atestado_em = timezone.now()
    medicao.save(update_fields=["status", "atestado_por", "atestado_em"])
    registrar_auditoria(
        municipio=municipio,
        modulo="CONTRATOS",
        evento="MEDICAO_ATESTADA",
        entidade="MedicaoContrato",
        entidade_id=medicao.pk,
        usuario=request.user,
        antes={"status": status_antes},
        depois={"status": medicao.status, "numero": medicao.numero, "contrato": medicao.contrato.numero},
    )
    publicar_evento_transparencia(
        municipio=municipio,
        modulo="CONTRATOS",
        tipo_evento="MEDICAO_ATESTADA",
        titulo=f"Medicao {medicao.numero} atestada",
        referencia=medicao.contrato.numero,
        valor=medicao.valor_medido,
        dados={"status": medicao.status, "contrato": medicao.contrato.numero},
    )
    messages.success(request, "Medicao atestada com sucesso.")
    return redirect(reverse("contratos:detail", args=[medicao.contrato_id]) + f"?municipio={municipio.pk}")


@login_required
@require_perm("contratos.manage")
def medicao_liquidar(request, medicao_pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    medicao = get_object_or_404(MedicaoContrato.objects.select_related("contrato", "contrato__empenho"), pk=medicao_pk)
    if medicao.contrato.municipio_id != municipio.id:
        return redirect("core:dashboard")
    if medicao.status != MedicaoContrato.Status.ATESTADA:
        messages.error(request, "A medicao precisa estar atestada antes da liquidacao.")
        return redirect(reverse("contratos:detail", args=[medicao.contrato_id]) + f"?municipio={municipio.pk}")
    if not medicao.contrato.empenho_id:
        messages.error(request, "O contrato precisa ter empenho vinculado para liquidar.")
        return redirect(reverse("contratos:detail", args=[medicao.contrato_id]) + f"?municipio={municipio.pk}")

    empenho = medicao.contrato.empenho
    if medicao.valor_medido > empenho.saldo_a_liquidar:
        messages.error(request, "Valor da medicao excede saldo a liquidar do empenho.")
        return redirect(reverse("contratos:detail", args=[medicao.contrato_id]) + f"?municipio={municipio.pk}")

    numero = f"LIQ-CONTR-{medicao.pk}-{timezone.now():%Y%m%d%H%M%S}"
    liquidacao = DespLiquidacao.objects.create(
        empenho=empenho,
        numero=numero,
        data_liquidacao=timezone.localdate(),
        observacao=f"Liquidacao automatica da medicao {medicao.numero} do contrato {medicao.contrato.numero}",
        valor_liquidado=medicao.valor_medido,
        criado_por=request.user,
    )
    registrar_liquidacao(liquidacao, usuario=request.user)

    medicao.status = MedicaoContrato.Status.LIQUIDADA
    medicao.liquidacao = liquidacao
    medicao.save(update_fields=["status", "liquidacao"])
    registrar_auditoria(
        municipio=municipio,
        modulo="CONTRATOS",
        evento="MEDICAO_LIQUIDADA",
        entidade="MedicaoContrato",
        entidade_id=medicao.pk,
        usuario=request.user,
        antes={"status": MedicaoContrato.Status.ATESTADA},
        depois={
            "status": medicao.status,
            "numero": medicao.numero,
            "liquidacao_numero": liquidacao.numero,
            "valor": str(medicao.valor_medido),
        },
    )
    publicar_evento_transparencia(
        municipio=municipio,
        modulo="CONTRATOS",
        tipo_evento="MEDICAO_LIQUIDADA",
        titulo=f"Medicao {medicao.numero} liquidada",
        descricao=f"Liquidacao: {liquidacao.numero}",
        referencia=medicao.contrato.numero,
        valor=medicao.valor_medido,
        dados={"liquidacao_numero": liquidacao.numero, "status": medicao.status},
    )

    messages.success(request, "Medicao liquidada no financeiro com sucesso.")
    return redirect(reverse("contratos:detail", args=[medicao.contrato_id]) + f"?municipio={municipio.pk}")
