from __future__ import annotations

from collections import defaultdict

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.core.decorators import require_perm
from apps.core.rbac import scope_filter_municipios, scope_filter_secretarias
from apps.org.forms import SecretariaCadastroBaseForm, SecretariaConfiguracaoForm
from apps.org.models import Municipio, Secretaria, SecretariaCadastroBase, SecretariaConfiguracao

from .views_common import ensure_municipio_scope_or_403, force_user_municipio_id


def _resolve_municipio(request):
    municipio_id = force_user_municipio_id(request.user, (request.GET.get("municipio") or "").strip())
    municipios_qs = scope_filter_municipios(request.user, Municipio.objects.filter(ativo=True).order_by("nome"))
    if municipio_id.isdigit():
        municipio = municipios_qs.filter(pk=int(municipio_id)).first()
        return municipio, municipios_qs
    return municipios_qs.first(), municipios_qs


def _secretaria_or_forbidden(request, secretaria_id: int) -> Secretaria:
    secretaria = get_object_or_404(
        scope_filter_secretarias(request.user, Secretaria.objects.select_related("municipio")),
        pk=secretaria_id,
    )
    block = ensure_municipio_scope_or_403(request.user, secretaria.municipio_id)
    if block:
        raise PermissionDenied("403 — Fora do seu município.")
    return secretaria


@require_perm("org.manage_secretaria")
@require_http_methods(["GET"])
def secretaria_governanca_hub(request):
    municipio, municipios = _resolve_municipio(request)
    q = (request.GET.get("q") or "").strip()

    qs = scope_filter_secretarias(
        request.user,
        Secretaria.objects.select_related("municipio").annotate(
            total_configuracoes=Count("configuracoes", distinct=True),
            total_cadastros=Count("cadastros_base", distinct=True),
            total_modulos=Count("modulos_ativos", filter=Q(modulos_ativos__ativo=True), distinct=True),
        ),
    )
    if municipio:
        qs = qs.filter(municipio=municipio)
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(sigla__icontains=q) | Q(tipo_modelo__icontains=q))

    return render(
        request,
        "org/secretaria_governanca_hub.html",
        {
            "title": "Governanca de Secretarias",
            "subtitle": "Editor operacional de configuracoes e cadastros-base por secretaria",
            "actions": [
                {
                    "label": "Organizacao",
                    "url": reverse("org:index"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
            "municipio": municipio,
            "municipios": municipios,
            "q": q,
            "items": qs.order_by("nome"),
        },
    )


@require_perm("org.manage_secretaria")
@require_http_methods(["GET"])
def secretaria_governanca_detail(request, secretaria_pk: int):
    secretaria = _secretaria_or_forbidden(request, secretaria_pk)
    configuracoes = secretaria.configuracoes.order_by("chave")
    cadastros = secretaria.cadastros_base.order_by("categoria", "ordem", "nome")

    cadastros_por_categoria: dict[str, list[SecretariaCadastroBase]] = defaultdict(list)
    for item in cadastros:
        cadastros_por_categoria[item.categoria or "GERAL"].append(item)

    return render(
        request,
        "org/secretaria_governanca_detail.html",
        {
            "title": f"Governanca • {secretaria.nome}",
            "subtitle": f"{secretaria.municipio.nome}/{secretaria.municipio.uf}",
            "secretaria": secretaria,
            "configuracoes": configuracoes,
            "cadastros_por_categoria": sorted(cadastros_por_categoria.items(), key=lambda x: x[0]),
            "actions": [
                {
                    "label": "Novo cadastro-base",
                    "url": reverse("org:secretaria_cadastro_base_create", args=[secretaria.pk]),
                    "icon": "fa-solid fa-list",
                    "variant": "btn-primary",
                },
                {
                    "label": "Nova configuracao",
                    "url": reverse("org:secretaria_configuracao_create", args=[secretaria.pk]),
                    "icon": "fa-solid fa-sliders",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Voltar",
                    "url": reverse("org:secretaria_governanca_hub") + f"?municipio={secretaria.municipio_id}",
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@require_perm("org.manage_secretaria")
@require_http_methods(["GET", "POST"])
def secretaria_configuracao_create(request, secretaria_pk: int):
    secretaria = _secretaria_or_forbidden(request, secretaria_pk)
    form = SecretariaConfiguracaoForm(request.POST or None, secretaria=secretaria, user=request.user)

    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.secretaria = secretaria
        obj.atualizado_por = request.user
        obj.save()
        messages.success(request, "Configuracao salva com sucesso.")
        return redirect("org:secretaria_governanca_detail", secretaria_pk=secretaria.pk)

    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Nova configuracao • {secretaria.nome}",
            "subtitle": "Configura parametros de governanca e funcionamento da secretaria",
            "actions": [],
            "form": form,
            "cancel_url": reverse("org:secretaria_governanca_detail", args=[secretaria.pk]),
            "submit_label": "Salvar configuracao",
        },
    )


@require_perm("org.manage_secretaria")
@require_http_methods(["GET", "POST"])
def secretaria_configuracao_update(request, pk: int):
    obj = get_object_or_404(SecretariaConfiguracao.objects.select_related("secretaria", "secretaria__municipio"), pk=pk)
    secretaria = _secretaria_or_forbidden(request, obj.secretaria_id)
    form = SecretariaConfiguracaoForm(request.POST or None, instance=obj, secretaria=secretaria, user=request.user)

    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.secretaria = secretaria
        obj.atualizado_por = request.user
        obj.save()
        messages.success(request, "Configuracao atualizada.")
        return redirect("org:secretaria_governanca_detail", secretaria_pk=secretaria.pk)

    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Editar configuracao • {secretaria.nome}",
            "subtitle": obj.chave,
            "actions": [],
            "form": form,
            "cancel_url": reverse("org:secretaria_governanca_detail", args=[secretaria.pk]),
            "submit_label": "Salvar alteracoes",
        },
    )


@require_perm("org.manage_secretaria")
@require_http_methods(["POST"])
def secretaria_configuracao_delete(request, pk: int):
    obj = get_object_or_404(SecretariaConfiguracao.objects.select_related("secretaria"), pk=pk)
    secretaria = _secretaria_or_forbidden(request, obj.secretaria_id)
    obj.delete()
    messages.success(request, "Configuracao removida.")
    return redirect("org:secretaria_governanca_detail", secretaria_pk=secretaria.pk)


@require_perm("org.manage_secretaria")
@require_http_methods(["GET", "POST"])
def secretaria_cadastro_base_create(request, secretaria_pk: int):
    secretaria = _secretaria_or_forbidden(request, secretaria_pk)
    form = SecretariaCadastroBaseForm(request.POST or None, secretaria=secretaria)

    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.secretaria = secretaria
        obj.save()
        messages.success(request, "Cadastro-base salvo com sucesso.")
        return redirect("org:secretaria_governanca_detail", secretaria_pk=secretaria.pk)

    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Novo cadastro-base • {secretaria.nome}",
            "subtitle": "Itens referenciais para uso nos modulos operacionais",
            "actions": [],
            "form": form,
            "cancel_url": reverse("org:secretaria_governanca_detail", args=[secretaria.pk]),
            "submit_label": "Salvar cadastro-base",
        },
    )


@require_perm("org.manage_secretaria")
@require_http_methods(["GET", "POST"])
def secretaria_cadastro_base_update(request, pk: int):
    obj = get_object_or_404(SecretariaCadastroBase.objects.select_related("secretaria", "secretaria__municipio"), pk=pk)
    secretaria = _secretaria_or_forbidden(request, obj.secretaria_id)
    form = SecretariaCadastroBaseForm(request.POST or None, instance=obj, secretaria=secretaria)

    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.secretaria = secretaria
        obj.save()
        messages.success(request, "Cadastro-base atualizado.")
        return redirect("org:secretaria_governanca_detail", secretaria_pk=secretaria.pk)

    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Editar cadastro-base • {secretaria.nome}",
            "subtitle": f"{obj.categoria} • {obj.nome}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("org:secretaria_governanca_detail", args=[secretaria.pk]),
            "submit_label": "Salvar alteracoes",
        },
    )


@require_perm("org.manage_secretaria")
@require_http_methods(["POST"])
def secretaria_cadastro_base_delete(request, pk: int):
    obj = get_object_or_404(SecretariaCadastroBase.objects.select_related("secretaria"), pk=pk)
    secretaria = _secretaria_or_forbidden(request, obj.secretaria_id)
    obj.delete()
    messages.success(request, "Cadastro-base removido.")
    return redirect("org:secretaria_governanca_detail", secretaria_pk=secretaria.pk)
