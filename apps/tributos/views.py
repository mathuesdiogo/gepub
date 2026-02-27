from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import require_perm
from apps.core.services_auditoria import registrar_auditoria
from apps.core.services_transparencia import publicar_evento_transparencia
from apps.core.rbac import is_admin
from apps.org.models import Municipio

from .forms import TributoLancamentoForm, TributosCadastroForm
from .models import TributoLancamento, TributosCadastro


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


@login_required
@require_perm("tributos.view")
def index(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    contribuintes = TributosCadastro.objects.filter(municipio=municipio)
    lancamentos = TributoLancamento.objects.filter(municipio=municipio)
    total_emitido = lancamentos.aggregate(t=Sum("valor_total"))["t"] or 0
    total_pago = lancamentos.filter(status=TributoLancamento.Status.PAGO).aggregate(t=Sum("valor_total"))["t"] or 0
    return render(
        request,
        "tributos/index.html",
        {
            "title": "Tributos Municipais",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "cards": [
                {"label": "Contribuintes ativos", "value": contribuintes.filter(status=TributosCadastro.Status.ATIVO).count()},
                {"label": "Lançamentos emitidos", "value": lancamentos.filter(status=TributoLancamento.Status.EMITIDO).count()},
                {"label": "Total emitido", "value": f"R$ {total_emitido}"},
                {"label": "Total arrecadado", "value": f"R$ {total_pago}"},
            ],
            "latest_lanc": lancamentos.select_related("contribuinte").order_by("-id")[:10],
            "actions": [
                {
                    "label": "Novo contribuinte",
                    "url": reverse("tributos:contribuinte_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Lançamentos",
                    "url": reverse("tributos:lancamento_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-receipt",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("tributos.view")
def contribuinte_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    qs = TributosCadastro.objects.filter(municipio=municipio)
    if q:
        qs = qs.filter(
            Q(codigo__icontains=q)
            | Q(nome__icontains=q)
            | Q(documento__icontains=q)
            | Q(inscricao_municipal__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)
    return render(
        request,
        "tributos/contribuinte_list.html",
        {
            "title": "Contribuintes",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("nome"),
            "q": q,
            "status": status,
            "status_choices": TributosCadastro.Status.choices,
            "actions": [
                {
                    "label": "Novo contribuinte",
                    "url": reverse("tributos:contribuinte_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            ],
        },
    )


@login_required
@require_perm("tributos.manage")
def contribuinte_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para cadastrar contribuinte.")
        return redirect("tributos:contribuinte_list")
    form = TributosCadastroForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        messages.success(request, "Contribuinte cadastrado.")
        return redirect(reverse("tributos:contribuinte_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo contribuinte",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("tributos:contribuinte_list") + _q_municipio(municipio),
            "submit_label": "Salvar contribuinte",
        },
    )


@login_required
@require_perm("tributos.manage")
def contribuinte_update(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(TributosCadastro, pk=pk, municipio=municipio)
    form = TributosCadastroForm(request.POST or None, instance=obj, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Contribuinte atualizado.")
        return redirect(reverse("tributos:contribuinte_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Editar contribuinte {obj.nome}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("tributos:contribuinte_list") + _q_municipio(municipio),
            "submit_label": "Salvar alterações",
        },
    )


@login_required
@require_perm("tributos.view")
def lancamento_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    status = (request.GET.get("status") or "").strip()
    tipo = (request.GET.get("tipo") or "").strip()
    q = (request.GET.get("q") or "").strip()
    qs = TributoLancamento.objects.filter(municipio=municipio).select_related("contribuinte")
    if status:
        qs = qs.filter(status=status)
    if tipo:
        qs = qs.filter(tipo_tributo=tipo)
    if q:
        qs = qs.filter(Q(contribuinte__nome__icontains=q) | Q(referencia__icontains=q))
    return render(
        request,
        "tributos/lancamento_list.html",
        {
            "title": "Lançamentos tributários",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-id"),
            "status": status,
            "tipo": tipo,
            "q": q,
            "status_choices": TributoLancamento.Status.choices,
            "tipo_choices": TributoLancamento.TipoTributo.choices,
            "actions": [
                {
                    "label": "Novo lançamento",
                    "url": reverse("tributos:lancamento_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            ],
        },
    )


@login_required
@require_perm("tributos.manage")
def lancamento_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para criar lançamento.")
        return redirect("tributos:lancamento_list")
    form = TributoLancamentoForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.status = TributoLancamento.Status.EMITIDO
        obj.save()
        publicar_evento_transparencia(
            municipio=municipio,
            modulo="TRIBUTOS",
            tipo_evento="LANCAMENTO_EMITIDO",
            titulo=f"Lançamento {obj.get_tipo_tributo_display()} emitido",
            referencia=obj.referencia or f"{obj.tipo_tributo}-{obj.pk}",
            valor=obj.valor_total,
            dados={"contribuinte": obj.contribuinte.nome, "exercicio": obj.exercicio},
            publico=False,
        )
        messages.success(request, "Lançamento emitido.")
        return redirect(reverse("tributos:lancamento_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo lançamento tributário",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("tributos:lancamento_list") + _q_municipio(municipio),
            "submit_label": "Salvar lançamento",
        },
    )


@login_required
@require_perm("tributos.manage")
@require_POST
def lancamento_baixar(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(TributoLancamento, pk=pk, municipio=municipio)
    if obj.status == TributoLancamento.Status.PAGO:
        messages.info(request, "Lançamento já está pago.")
        return redirect(reverse("tributos:lancamento_list") + _q_municipio(municipio))
    obj.status = TributoLancamento.Status.PAGO
    obj.data_pagamento = timezone.localdate()
    obj.save(update_fields=["status", "data_pagamento", "atualizado_em"])
    registrar_auditoria(
        municipio=municipio,
        modulo="TRIBUTOS",
        evento="LANCAMENTO_BAIXADO",
        entidade="TributoLancamento",
        entidade_id=obj.pk,
        usuario=request.user,
        depois={"status": obj.status, "valor_total": str(obj.valor_total)},
    )
    messages.success(request, "Pagamento baixado com sucesso.")
    return redirect(reverse("tributos:lancamento_list") + _q_municipio(municipio))


# compatibilidade com rota antiga
create = contribuinte_create
