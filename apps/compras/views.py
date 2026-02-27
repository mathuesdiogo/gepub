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
from apps.financeiro.models import DespEmpenho
from apps.financeiro.services import registrar_empenho
from apps.org.models import Municipio

from .forms import ProcessoLicitatorioForm, RequisicaoCompraForm, RequisicaoCompraItemForm
from .models import ProcessoLicitatorio, RequisicaoCompra


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
@require_perm("compras.view")
def index(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    return redirect(reverse("compras:requisicao_list") + f"?municipio={municipio.pk}")


@login_required
@require_perm("compras.view")
def requisicao_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()

    qs = RequisicaoCompra.objects.filter(municipio=municipio).select_related("setor", "dotacao", "empenho")
    if q:
        qs = qs.filter(Q(numero__icontains=q) | Q(objeto__icontains=q) | Q(fornecedor_nome__icontains=q))
    if status:
        qs = qs.filter(status=status)

    return render(
        request,
        "compras/requisicao_list.html",
        {
            "title": "Compras e Requisicoes",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-criado_em"),
            "q": q,
            "status": status,
            "status_choices": RequisicaoCompra.Status.choices,
            "actions": [
                {
                    "label": "Nova requisicao",
                    "url": reverse("compras:requisicao_create") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Licitacoes",
                    "url": reverse("compras:licitacao_list") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-gavel",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("compras.manage")
def requisicao_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um municipio para criar requisicao.")
        return redirect("compras:requisicao_list")

    form = RequisicaoCompraForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        if obj.status == RequisicaoCompra.Status.APROVADA:
            obj.aprovado_por = request.user
            obj.aprovado_em = timezone.now()
        obj.save()
        registrar_auditoria(
            municipio=municipio,
            modulo="COMPRAS",
            evento="REQUISICAO_CRIADA",
            entidade="RequisicaoCompra",
            entidade_id=obj.pk,
            usuario=request.user,
            depois={
                "numero": obj.numero,
                "status": obj.status,
                "valor_estimado": str(obj.valor_estimado),
                "dotacao_id": obj.dotacao_id,
            },
        )
        publicar_evento_transparencia(
            municipio=municipio,
            modulo="COMPRAS",
            tipo_evento="REQUISICAO_CRIADA",
            titulo=f"Requisicao de compra {obj.numero} registrada",
            descricao=obj.objeto,
            referencia=obj.numero,
            valor=obj.valor_estimado,
            dados={
                "status": obj.status,
                "dotacao_id": obj.dotacao_id,
                "setor_id": obj.setor_id,
            },
        )
        messages.success(request, "Requisicao criada com sucesso.")
        return redirect(reverse("compras:requisicao_detail", args=[obj.pk]) + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova requisicao de compra",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("compras:requisicao_list") + f"?municipio={municipio.pk}",
            "submit_label": "Salvar requisicao",
        },
    )


@login_required
@require_perm("compras.view")
def requisicao_detail(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    obj = get_object_or_404(
        RequisicaoCompra.objects.select_related("processo", "setor", "dotacao", "empenho"),
        pk=pk,
        municipio=municipio,
    )

    valor_base = obj.valor_estimado or obj.valor_itens
    pode_empenhar = obj.status in {RequisicaoCompra.Status.APROVADA, RequisicaoCompra.Status.HOMOLOGADA} and not obj.empenho_id

    actions = [
        {
            "label": "Adicionar item",
            "url": reverse("compras:item_create", args=[obj.pk]) + f"?municipio={municipio.pk}",
            "icon": "fa-solid fa-list-check",
            "variant": "btn-primary",
        },
        {
            "label": "Aprovar",
            "url": reverse("compras:aprovar", args=[obj.pk]) + f"?municipio={municipio.pk}",
            "icon": "fa-solid fa-circle-check",
            "variant": "btn--ghost",
        },
    ]
    if pode_empenhar:
        actions.append(
            {
                "label": "Gerar empenho",
                "url": reverse("compras:gerar_empenho", args=[obj.pk]) + f"?municipio={municipio.pk}",
                "icon": "fa-solid fa-file-signature",
                "variant": "btn--ghost",
            }
        )
    actions.append(
        {
            "label": "Voltar",
            "url": reverse("compras:requisicao_list") + f"?municipio={municipio.pk}",
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }
    )

    fields = [
        {"label": "Numero", "value": obj.numero},
        {"label": "Objeto", "value": obj.objeto},
        {"label": "Processo", "value": obj.processo or "-"},
        {"label": "Setor", "value": obj.setor or "-"},
        {"label": "Fornecedor", "value": obj.fornecedor_nome or "-"},
        {"label": "Documento fornecedor", "value": obj.fornecedor_documento or "-"},
        {"label": "Dotacao", "value": obj.dotacao or "-"},
        {"label": "Empenho", "value": obj.empenho or "-"},
    ]
    pills = [
        {"label": "Status", "value": obj.get_status_display()},
        {"label": "Valor estimado", "value": obj.valor_estimado},
        {"label": "Valor itens", "value": obj.valor_itens},
        {"label": "Valor base", "value": valor_base},
    ]

    return render(
        request,
        "compras/requisicao_detail.html",
        {
            "title": f"Requisicao {obj.numero}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": actions,
            "obj": obj,
            "fields": fields,
            "pills": pills,
            "itens": obj.itens.order_by("id"),
            "municipio": municipio,
        },
    )


@login_required
@require_perm("compras.manage")
def item_create(request, requisicao_pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    req = get_object_or_404(RequisicaoCompra, pk=requisicao_pk, municipio=municipio)
    form = RequisicaoCompraItemForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.requisicao = req
        item.save()
        messages.success(request, "Item adicionado com sucesso.")
        return redirect(reverse("compras:requisicao_detail", args=[req.pk]) + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Novo item - Requisicao {req.numero}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("compras:requisicao_detail", args=[req.pk]) + f"?municipio={municipio.pk}",
            "submit_label": "Salvar item",
        },
    )


@login_required
@require_perm("compras.manage")
def aprovar(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    req = get_object_or_404(RequisicaoCompra, pk=pk, municipio=municipio)
    status_antes = req.status
    req.status = RequisicaoCompra.Status.APROVADA
    req.aprovado_por = request.user
    req.aprovado_em = timezone.now()
    req.save(update_fields=["status", "aprovado_por", "aprovado_em", "atualizado_em"])
    registrar_auditoria(
        municipio=municipio,
        modulo="COMPRAS",
        evento="REQUISICAO_APROVADA",
        entidade="RequisicaoCompra",
        entidade_id=req.pk,
        usuario=request.user,
        antes={"status": status_antes},
        depois={"status": req.status, "numero": req.numero},
    )
    publicar_evento_transparencia(
        municipio=municipio,
        modulo="COMPRAS",
        tipo_evento="REQUISICAO_APROVADA",
        titulo=f"Requisicao {req.numero} aprovada",
        referencia=req.numero,
        valor=req.valor_estimado if req.valor_estimado > 0 else req.valor_itens,
        dados={"status": req.status},
    )
    messages.success(request, "Requisicao aprovada.")
    return redirect(reverse("compras:requisicao_detail", args=[req.pk]) + f"?municipio={municipio.pk}")


@login_required
@require_perm("compras.manage")
def gerar_empenho(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    req = get_object_or_404(
        RequisicaoCompra.objects.select_related("dotacao", "dotacao__exercicio", "dotacao__unidade_gestora"),
        pk=pk,
        municipio=municipio,
    )
    if req.empenho_id:
        messages.info(request, "Esta requisicao ja possui empenho vinculado.")
        return redirect(reverse("compras:requisicao_detail", args=[req.pk]) + f"?municipio={municipio.pk}")
    if req.status not in {RequisicaoCompra.Status.APROVADA, RequisicaoCompra.Status.HOMOLOGADA}:
        messages.error(request, "A requisicao precisa estar aprovada para gerar empenho.")
        return redirect(reverse("compras:requisicao_detail", args=[req.pk]) + f"?municipio={municipio.pk}")
    if not req.dotacao_id:
        messages.error(request, "Informe uma dotacao na requisicao antes de gerar empenho.")
        return redirect(reverse("compras:requisicao_detail", args=[req.pk]) + f"?municipio={municipio.pk}")

    valor = req.valor_estimado if req.valor_estimado > 0 else req.valor_itens
    if valor <= 0:
        messages.error(request, "Nao e possivel gerar empenho com valor zero.")
        return redirect(reverse("compras:requisicao_detail", args=[req.pk]) + f"?municipio={municipio.pk}")
    if valor > req.dotacao.saldo_disponivel:
        messages.error(request, "Valor da requisicao excede saldo disponivel da dotacao.")
        return redirect(reverse("compras:requisicao_detail", args=[req.pk]) + f"?municipio={municipio.pk}")

    numero = f"EMP-COMPRA-{req.pk}-{timezone.now():%Y%m%d%H%M%S}"
    empenho = DespEmpenho.objects.create(
        municipio=municipio,
        exercicio=req.dotacao.exercicio,
        unidade_gestora=req.dotacao.unidade_gestora,
        dotacao=req.dotacao,
        numero=numero,
        fornecedor_nome=req.fornecedor_nome or "Fornecedor nao informado",
        fornecedor_documento=req.fornecedor_documento,
        objeto=req.objeto,
        tipo=DespEmpenho.Tipo.ORDINARIO,
        valor_empenhado=valor,
        criado_por=request.user,
    )
    registrar_empenho(empenho, usuario=request.user)

    status_antes = req.status
    req.empenho = empenho
    req.status = RequisicaoCompra.Status.HOMOLOGADA
    req.save(update_fields=["empenho", "status", "atualizado_em"])
    registrar_auditoria(
        municipio=municipio,
        modulo="COMPRAS",
        evento="REQUISICAO_HOMOLOGADA_COM_EMPENHO",
        entidade="RequisicaoCompra",
        entidade_id=req.pk,
        usuario=request.user,
        antes={"status": status_antes},
        depois={
            "status": req.status,
            "numero": req.numero,
            "empenho_numero": empenho.numero,
            "valor": str(valor),
        },
    )
    publicar_evento_transparencia(
        municipio=municipio,
        modulo="COMPRAS",
        tipo_evento="REQUISICAO_HOMOLOGADA",
        titulo=f"Requisicao {req.numero} homologada",
        descricao=f"Empenho gerado: {empenho.numero}",
        referencia=req.numero,
        valor=valor,
        dados={
            "status": req.status,
            "empenho_numero": empenho.numero,
        },
    )

    messages.success(request, "Empenho gerado e vinculado com sucesso.")
    return redirect(reverse("compras:requisicao_detail", args=[req.pk]) + f"?municipio={municipio.pk}")


@login_required
@require_perm("compras.view")
def licitacao_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    qs = ProcessoLicitatorio.objects.filter(municipio=municipio).select_related("requisicao")
    if q:
        qs = qs.filter(Q(numero_processo__icontains=q) | Q(objeto__icontains=q) | Q(vencedor_nome__icontains=q))

    return render(
        request,
        "compras/licitacao_list.html",
        {
            "title": "Licitacoes e Dispensas",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-data_abertura", "-id"),
            "q": q,
            "actions": [
                {
                    "label": "Nova licitacao",
                    "url": reverse("compras:licitacao_create") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Requisicoes",
                    "url": reverse("compras:requisicao_list") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("compras.manage")
def licitacao_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um municipio para criar licitacao.")
        return redirect("compras:licitacao_list")

    form = ProcessoLicitatorioForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.save()
        registrar_auditoria(
            municipio=municipio,
            modulo="COMPRAS",
            evento="LICITACAO_CRIADA",
            entidade="ProcessoLicitatorio",
            entidade_id=obj.pk,
            usuario=request.user,
            depois={
                "numero_processo": obj.numero_processo,
                "modalidade": obj.modalidade,
                "status": obj.status,
            },
        )
        publicar_evento_transparencia(
            municipio=municipio,
            modulo="COMPRAS",
            tipo_evento="LICITACAO_CRIADA",
            titulo=f"Processo licitatorio {obj.numero_processo} cadastrado",
            descricao=f"Modalidade: {obj.get_modalidade_display()}",
            referencia=obj.numero_processo,
            dados={"status": obj.status, "modalidade": obj.modalidade},
        )
        messages.success(request, "Processo licitatorio criado com sucesso.")
        return redirect(reverse("compras:licitacao_list") + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova licitacao",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("compras:licitacao_list") + f"?municipio={municipio.pk}",
            "submit_label": "Salvar licitacao",
        },
    )
