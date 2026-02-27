from __future__ import annotations

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

from .forms import FrotaAbastecimentoForm, FrotaCadastroForm, FrotaManutencaoForm, FrotaViagemForm
from .models import FrotaAbastecimento, FrotaCadastro, FrotaManutencao, FrotaViagem


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
@require_perm("frota.view")
def index(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    veiculos = FrotaCadastro.objects.filter(municipio=municipio)
    viagens = FrotaViagem.objects.filter(municipio=municipio)
    manut = FrotaManutencao.objects.filter(municipio=municipio)
    abast = FrotaAbastecimento.objects.filter(municipio=municipio)
    return render(
        request,
        "frota/index.html",
        {
            "title": "Gestão de Frota",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "cards": [
                {"label": "Veículos ativos", "value": veiculos.filter(status=FrotaCadastro.Status.ATIVO).count()},
                {"label": "Em manutenção", "value": veiculos.filter(situacao=FrotaCadastro.Situacao.MANUTENCAO).count()},
                {"label": "Viagens abertas", "value": viagens.filter(status=FrotaViagem.Status.ABERTA).count()},
                {"label": "Abastecimentos mês", "value": abast.filter(data_abastecimento__month=timezone.localdate().month).count()},
            ],
            "latest_viagens": viagens.select_related("veiculo", "motorista").order_by("-data_saida", "-id")[:8],
            "latest_manut": manut.select_related("veiculo").order_by("-data_inicio", "-id")[:8],
            "actions": [
                {
                    "label": "Novo veículo",
                    "url": reverse("frota:veiculo_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Viagens",
                    "url": reverse("frota:viagem_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-route",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Manutenções",
                    "url": reverse("frota:manutencao_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-screwdriver-wrench",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("frota.view")
def veiculo_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    q = (request.GET.get("q") or "").strip()
    situacao = (request.GET.get("situacao") or "").strip()
    qs = FrotaCadastro.objects.filter(municipio=municipio)
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(placa__icontains=q) | Q(nome__icontains=q) | Q(marca_modelo__icontains=q))
    if situacao:
        qs = qs.filter(situacao=situacao)
    return render(
        request,
        "frota/veiculo_list.html",
        {
            "title": "Veículos",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("nome"),
            "q": q,
            "situacao": situacao,
            "situacao_choices": FrotaCadastro.Situacao.choices,
            "actions": [
                {
                    "label": "Novo veículo",
                    "url": reverse("frota:veiculo_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            ],
        },
    )


@login_required
@require_perm("frota.manage")
def veiculo_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para cadastrar veículo.")
        return redirect("frota:veiculo_list")
    form = FrotaCadastroForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        messages.success(request, "Veículo salvo.")
        return redirect(reverse("frota:veiculo_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo veículo",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("frota:veiculo_list") + _q_municipio(municipio),
            "submit_label": "Salvar veículo",
        },
    )


@login_required
@require_perm("frota.manage")
def veiculo_update(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(FrotaCadastro, pk=pk, municipio=municipio)
    form = FrotaCadastroForm(request.POST or None, instance=obj, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Veículo atualizado.")
        return redirect(reverse("frota:veiculo_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Editar veículo {obj.codigo}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("frota:veiculo_list") + _q_municipio(municipio),
            "submit_label": "Salvar alterações",
        },
    )


@login_required
@require_perm("frota.view")
def abastecimento_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    q = (request.GET.get("q") or "").strip()
    qs = FrotaAbastecimento.objects.filter(municipio=municipio).select_related("veiculo")
    if q:
        qs = qs.filter(Q(veiculo__codigo__icontains=q) | Q(veiculo__placa__icontains=q) | Q(posto__icontains=q))
    return render(
        request,
        "frota/abastecimento_list.html",
        {
            "title": "Abastecimentos",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-data_abastecimento", "-id"),
            "q": q,
            "actions": [
                {
                    "label": "Novo abastecimento",
                    "url": reverse("frota:abastecimento_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            ],
        },
    )


@login_required
@require_perm("frota.manage")
def abastecimento_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para registrar abastecimento.")
        return redirect("frota:abastecimento_list")
    form = FrotaAbastecimentoForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        veiculo = obj.veiculo
        if obj.quilometragem and obj.quilometragem > veiculo.quilometragem_atual:
            veiculo.quilometragem_atual = obj.quilometragem
            veiculo.save(update_fields=["quilometragem_atual", "atualizado_em"])
        messages.success(request, "Abastecimento registrado.")
        return redirect(reverse("frota:abastecimento_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo abastecimento",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("frota:abastecimento_list") + _q_municipio(municipio),
            "submit_label": "Salvar abastecimento",
        },
    )


@login_required
@require_perm("frota.view")
def manutencao_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    status = (request.GET.get("status") or "").strip()
    qs = FrotaManutencao.objects.filter(municipio=municipio).select_related("veiculo")
    if status:
        qs = qs.filter(status=status)
    return render(
        request,
        "frota/manutencao_list.html",
        {
            "title": "Manutenções",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-data_inicio", "-id"),
            "status": status,
            "status_choices": FrotaManutencao.Status.choices,
            "actions": [
                {
                    "label": "Nova manutenção",
                    "url": reverse("frota:manutencao_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            ],
        },
    )


@login_required
@require_perm("frota.manage")
def manutencao_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para registrar manutenção.")
        return redirect("frota:manutencao_list")
    form = FrotaManutencaoForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.status = FrotaManutencao.Status.ABERTA
        obj.save()
        obj.veiculo.situacao = FrotaCadastro.Situacao.MANUTENCAO
        obj.veiculo.save(update_fields=["situacao", "atualizado_em"])
        messages.success(request, "Manutenção registrada.")
        return redirect(reverse("frota:manutencao_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova manutenção",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("frota:manutencao_list") + _q_municipio(municipio),
            "submit_label": "Salvar manutenção",
        },
    )


@login_required
@require_perm("frota.manage")
@require_POST
def manutencao_concluir(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(FrotaManutencao, pk=pk, municipio=municipio)
    obj.status = FrotaManutencao.Status.CONCLUIDA
    obj.data_fim = obj.data_fim or timezone.localdate()
    obj.save(update_fields=["status", "data_fim", "atualizado_em"])
    obj.veiculo.situacao = FrotaCadastro.Situacao.DISPONIVEL
    obj.veiculo.save(update_fields=["situacao", "atualizado_em"])
    messages.success(request, "Manutenção concluída.")
    return redirect(reverse("frota:manutencao_list") + _q_municipio(municipio))


@login_required
@require_perm("frota.view")
def viagem_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    status = (request.GET.get("status") or "").strip()
    qs = FrotaViagem.objects.filter(municipio=municipio).select_related("veiculo", "motorista")
    if status:
        qs = qs.filter(status=status)
    return render(
        request,
        "frota/viagem_list.html",
        {
            "title": "Viagens",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-data_saida", "-id"),
            "status": status,
            "status_choices": FrotaViagem.Status.choices,
            "actions": [
                {
                    "label": "Nova viagem",
                    "url": reverse("frota:viagem_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            ],
        },
    )


@login_required
@require_perm("frota.manage")
def viagem_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para registrar viagem.")
        return redirect("frota:viagem_list")
    form = FrotaViagemForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.status = FrotaViagem.Status.ABERTA
        obj.save()
        messages.success(request, "Viagem registrada.")
        return redirect(reverse("frota:viagem_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova viagem",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("frota:viagem_list") + _q_municipio(municipio),
            "submit_label": "Salvar viagem",
        },
    )


@login_required
@require_perm("frota.manage")
@require_POST
def viagem_concluir(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(FrotaViagem, pk=pk, municipio=municipio)
    if obj.status != FrotaViagem.Status.ABERTA:
        messages.warning(request, "Viagem já finalizada/cancelada.")
        return redirect(reverse("frota:viagem_list") + _q_municipio(municipio))
    obj.status = FrotaViagem.Status.CONCLUIDA
    obj.data_retorno = obj.data_retorno or timezone.localdate()
    obj.save(update_fields=["status", "data_retorno", "atualizado_em"])
    if obj.km_retorno and obj.km_retorno > obj.veiculo.quilometragem_atual:
        obj.veiculo.quilometragem_atual = obj.km_retorno
        obj.veiculo.save(update_fields=["quilometragem_atual", "atualizado_em"])
    publicar_evento_transparencia(
        municipio=municipio,
        modulo="FROTA",
        tipo_evento="VIAGEM_CONCLUIDA",
        titulo=f"Viagem concluída para {obj.destino}",
        referencia=str(obj.pk),
        dados={"veiculo": obj.veiculo.codigo, "motorista": obj.motorista.username},
        publico=False,
    )
    registrar_auditoria(
        municipio=municipio,
        modulo="FROTA",
        evento="VIAGEM_CONCLUIDA",
        entidade="FrotaViagem",
        entidade_id=obj.pk,
        usuario=request.user,
        depois={"status": obj.status, "destino": obj.destino},
    )
    messages.success(request, "Viagem concluída.")
    return redirect(reverse("frota:viagem_list") + _q_municipio(municipio))


# compatibilidade com rota antiga
create = veiculo_create
