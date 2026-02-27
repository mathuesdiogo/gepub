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

from .forms import PatrimonioCadastroForm, PatrimonioInventarioForm, PatrimonioMovimentacaoForm
from .models import PatrimonioCadastro, PatrimonioInventario, PatrimonioMovimentacao


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
@require_perm("patrimonio.view")
def index(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    bens = PatrimonioCadastro.objects.filter(municipio=municipio)
    movs = PatrimonioMovimentacao.objects.filter(municipio=municipio)
    invs = PatrimonioInventario.objects.filter(municipio=municipio)
    return render(
        request,
        "patrimonio/index.html",
        {
            "title": "Patrimônio",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "cards": [
                {"label": "Bens ativos", "value": bens.filter(status=PatrimonioCadastro.Status.ATIVO).count()},
                {"label": "Em manutenção", "value": bens.filter(situacao=PatrimonioCadastro.Situacao.MANUTENCAO).count()},
                {"label": "Movimentações mês", "value": movs.filter(data_movimento__month=timezone.localdate().month).count()},
                {"label": "Inventários abertos", "value": invs.filter(status=PatrimonioInventario.Status.ABERTO).count()},
            ],
            "latest_movs": movs.select_related("bem").order_by("-data_movimento", "-id")[:10],
            "latest_invs": invs.order_by("-criado_em")[:8],
            "actions": [
                {
                    "label": "Novo bem",
                    "url": reverse("patrimonio:bem_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Movimentações",
                    "url": reverse("patrimonio:movimentacao_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-right-left",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Inventários",
                    "url": reverse("patrimonio:inventario_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-clipboard-check",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("patrimonio.view")
def bem_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    q = (request.GET.get("q") or "").strip()
    situacao = (request.GET.get("situacao") or "").strip()
    qs = PatrimonioCadastro.objects.filter(municipio=municipio).select_related("secretaria", "unidade")
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(tombo__icontains=q) | Q(nome__icontains=q))
    if situacao:
        qs = qs.filter(situacao=situacao)
    return render(
        request,
        "patrimonio/bem_list.html",
        {
            "title": "Bens patrimoniais",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("nome"),
            "q": q,
            "situacao": situacao,
            "situacao_choices": PatrimonioCadastro.Situacao.choices,
            "actions": [
                {
                    "label": "Novo bem",
                    "url": reverse("patrimonio:bem_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Painel patrimônio",
                    "url": reverse("patrimonio:index") + _q_municipio(municipio),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("patrimonio.manage")
def bem_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para cadastrar bem.")
        return redirect("patrimonio:bem_list")
    form = PatrimonioCadastroForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        messages.success(request, "Bem patrimonial cadastrado.")
        return redirect(reverse("patrimonio:bem_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo bem patrimonial",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("patrimonio:bem_list") + _q_municipio(municipio),
            "submit_label": "Salvar bem",
        },
    )


@login_required
@require_perm("patrimonio.manage")
def bem_update(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(PatrimonioCadastro, pk=pk, municipio=municipio)
    form = PatrimonioCadastroForm(request.POST or None, instance=obj, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Bem atualizado.")
        return redirect(reverse("patrimonio:bem_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Editar bem {obj.codigo}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("patrimonio:bem_list") + _q_municipio(municipio),
            "submit_label": "Salvar alterações",
        },
    )


@login_required
@require_perm("patrimonio.view")
def movimentacao_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    tipo = (request.GET.get("tipo") or "").strip()
    q = (request.GET.get("q") or "").strip()
    qs = PatrimonioMovimentacao.objects.filter(municipio=municipio).select_related("bem", "unidade_origem", "unidade_destino")
    if tipo:
        qs = qs.filter(tipo=tipo)
    if q:
        qs = qs.filter(Q(bem__nome__icontains=q) | Q(observacao__icontains=q))
    return render(
        request,
        "patrimonio/movimentacao_list.html",
        {
            "title": "Movimentações patrimoniais",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-data_movimento", "-id"),
            "tipo": tipo,
            "q": q,
            "tipo_choices": PatrimonioMovimentacao.Tipo.choices,
            "actions": [
                {
                    "label": "Nova movimentação",
                    "url": reverse("patrimonio:movimentacao_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            ],
        },
    )


@login_required
@require_perm("patrimonio.manage")
def movimentacao_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para criar movimentação.")
        return redirect("patrimonio:movimentacao_list")
    form = PatrimonioMovimentacaoForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()

        bem = obj.bem
        if obj.tipo == PatrimonioMovimentacao.Tipo.BAIXA:
            bem.situacao = PatrimonioCadastro.Situacao.BAIXADO
            bem.status = PatrimonioCadastro.Status.INATIVO
            bem.save(update_fields=["situacao", "status", "atualizado_em"])
        elif obj.tipo == PatrimonioMovimentacao.Tipo.MANUTENCAO:
            bem.situacao = PatrimonioCadastro.Situacao.MANUTENCAO
            bem.save(update_fields=["situacao", "atualizado_em"])
        elif obj.tipo == PatrimonioMovimentacao.Tipo.TRANSFERENCIA and obj.unidade_destino_id:
            bem.unidade_id = obj.unidade_destino_id
            bem.situacao = PatrimonioCadastro.Situacao.EM_USO
            bem.save(update_fields=["unidade", "situacao", "atualizado_em"])

        registrar_auditoria(
            municipio=municipio,
            modulo="PATRIMONIO",
            evento="MOVIMENTACAO_REGISTRADA",
            entidade="PatrimonioMovimentacao",
            entidade_id=obj.pk,
            usuario=request.user,
            depois={"tipo": obj.tipo, "bem": obj.bem.codigo},
        )
        messages.success(request, "Movimentação patrimonial registrada.")
        return redirect(reverse("patrimonio:movimentacao_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova movimentação patrimonial",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("patrimonio:movimentacao_list") + _q_municipio(municipio),
            "submit_label": "Salvar movimentação",
        },
    )


@login_required
@require_perm("patrimonio.view")
def inventario_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    status = (request.GET.get("status") or "").strip()
    qs = PatrimonioInventario.objects.filter(municipio=municipio)
    if status:
        qs = qs.filter(status=status)
    return render(
        request,
        "patrimonio/inventario_list.html",
        {
            "title": "Inventários patrimoniais",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-criado_em"),
            "status": status,
            "status_choices": PatrimonioInventario.Status.choices,
            "actions": [
                {
                    "label": "Novo inventário",
                    "url": reverse("patrimonio:inventario_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            ],
        },
    )


@login_required
@require_perm("patrimonio.manage")
def inventario_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para abrir inventário.")
        return redirect("patrimonio:inventario_list")
    form = PatrimonioInventarioForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        messages.success(request, "Inventário aberto com sucesso.")
        return redirect(reverse("patrimonio:inventario_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo inventário patrimonial",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("patrimonio:inventario_list") + _q_municipio(municipio),
            "submit_label": "Salvar inventário",
        },
    )


@login_required
@require_perm("patrimonio.manage")
@require_POST
def inventario_concluir(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(PatrimonioInventario, pk=pk, municipio=municipio)
    qs_bens = PatrimonioCadastro.objects.filter(municipio=municipio)
    if obj.unidade_id:
        qs_bens = qs_bens.filter(unidade_id=obj.unidade_id)
    obj.total_bens = qs_bens.count()
    obj.total_bens_ativos = qs_bens.filter(status=PatrimonioCadastro.Status.ATIVO).count()
    obj.status = PatrimonioInventario.Status.CONCLUIDO
    obj.concluido_em = timezone.now()
    obj.concluido_por = request.user
    obj.save(
        update_fields=[
            "total_bens",
            "total_bens_ativos",
            "status",
            "concluido_em",
            "concluido_por",
            "atualizado_em",
        ]
    )
    publicar_evento_transparencia(
        municipio=municipio,
        modulo="PATRIMONIO",
        tipo_evento="INVENTARIO_CONCLUIDO",
        titulo=f"Inventário {obj.codigo} concluído",
        referencia=obj.codigo,
        dados={"total_bens": obj.total_bens, "total_bens_ativos": obj.total_bens_ativos},
        publico=False,
    )
    messages.success(request, "Inventário concluído.")
    return redirect(reverse("patrimonio:inventario_list") + _q_municipio(municipio))


# compatibilidade com rota antiga
create = bem_create
