from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import can, scope_filter_unidades
from apps.org.models import Unidade
from .forms import UnidadeSaudeForm


@login_required
@require_perm("saude.view")
def unidade_list(request):
    q = (request.GET.get("q") or "").strip()

    qs = Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE).select_related("secretaria", "secretaria__municipio")

    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(secretaria__nome__icontains=q) | Q(secretaria__municipio__nome__icontains=q))

    qs = scope_filter_unidades(request.user, qs)

    paginator = Paginator(qs.order_by("nome"), 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    can_manage = can(request.user, "saude.manage")

    actions = []
    if can_manage:
        actions.append({"label": "Nova Unidade", "url": reverse("saude:unidade_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})

    headers = [{"label": "Unidade"}, {"label": "Secretaria"}, {"label": "Município"}, {"label": "Ativo", "width": "120px"}]
    rows = []
    for u in page_obj:
        rows.append({
            "cells": [
                {"text": u.nome, "url": reverse("saude:unidade_detail", args=[u.pk])},
                {"text": getattr(u.secretaria, "nome", "—")},
                {"text": getattr(getattr(u.secretaria, "municipio", None), "nome", "—")},
                {"text": "Sim" if getattr(u, "ativo", False) else "Não"},
            ],
            "can_edit": bool(can_manage and u.pk),
            "edit_url": reverse("saude:unidade_update", args=[u.pk]) if u.pk else "",
        })

    return render(request, "saude/unidade_list.html", {
        "q": q,
        "page_obj": page_obj,
        "actions": actions,
        "headers": headers,
        "rows": rows,
        "action_url": reverse("saude:unidade_list"),
        "clear_url": reverse("saude:unidade_list"),
        "has_filters": bool(q),
    })


@login_required
@require_perm("saude.view")
def unidade_detail(request, pk: int):
    qs = Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE).select_related("secretaria", "secretaria__municipio")
    qs = scope_filter_unidades(request.user, qs)
    unidade = get_object_or_404(qs, pk=pk)

    can_manage = can(request.user, "saude.manage")

    actions = [{"label": "Voltar", "url": reverse("saude:unidade_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if can_manage:
        actions.append({"label": "Editar", "url": reverse("saude:unidade_update", args=[unidade.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})

    fields = [
        {"label": "Secretaria", "value": getattr(unidade.secretaria, "nome", "—")},
        {"label": "Município", "value": getattr(getattr(unidade.secretaria, "municipio", None), "nome", "—")},
        {"label": "Telefone", "value": getattr(unidade, "telefone", "—") or "—"},
        {"label": "Endereço", "value": getattr(unidade, "endereco", "—") or "—"},
    ]
    pills = [{"label": "Status", "value": "Ativo" if getattr(unidade, "ativo", False) else "Inativo", "variant": "success" if getattr(unidade, "ativo", False) else "danger"}]

    return render(request, "saude/unidade_detail.html", {"unidade": unidade, "fields": fields, "pills": pills, "actions": actions})


@login_required
@require_perm("saude.manage")
def unidade_create(request):
    cancel_url = reverse("saude:unidade_list")

    if request.method == "POST":
        form = UnidadeSaudeForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tipo = Unidade.Tipo.SAUDE
            obj.save()
            messages.success(request, "Unidade de Saúde criada com sucesso.")
            return redirect("saude:unidade_detail", obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = UnidadeSaudeForm()

    return render(request, "saude/unidade_form.html", {"form": form, "mode": "create", "cancel_url": cancel_url})


@login_required
@require_perm("saude.manage")
def unidade_update(request, pk: int):
    qs = Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE)
    qs = scope_filter_unidades(request.user, qs)
    unidade = get_object_or_404(qs, pk=pk)

    cancel_url = reverse("saude:unidade_detail", args=[unidade.pk])

    if request.method == "POST":
        form = UnidadeSaudeForm(request.POST, instance=unidade)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tipo = Unidade.Tipo.SAUDE
            obj.save()
            messages.success(request, "Unidade de Saúde atualizada com sucesso.")
            return redirect("saude:unidade_detail", obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = UnidadeSaudeForm(instance=unidade)

    return render(request, "saude/unidade_form.html", {"form": form, "mode": "update", "cancel_url": cancel_url, "unidade": unidade})
