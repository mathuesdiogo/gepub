from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import can

from .forms import EspecialidadeSaudeForm
from .models import EspecialidadeSaude


@login_required
@require_perm("saude.view")
def especialidade_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = EspecialidadeSaude.objects.all().order_by("nome")
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(cbo__icontains=q))

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    can_manage = can(request.user, "saude.manage")
    actions = []
    if can_manage:
        actions.append({"label": "Nova Especialidade", "url": reverse("saude:especialidade_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})

    headers = [
        {"label": "Nome"},
        {"label": "CBO", "width": "180px"},
        {"label": "Ativo", "width": "120px"},
    ]
    rows = []
    for e in page_obj:
        rows.append(
            {
                "cells": [
                    {"text": e.nome, "url": reverse("saude:especialidade_detail", args=[e.pk])},
                    {"text": e.cbo or "—"},
                    {"text": "Sim" if e.ativo else "Não"},
                ],
                "can_edit": bool(can_manage),
                "edit_url": reverse("saude:especialidade_update", args=[e.pk]) if can_manage else "",
            }
        )

    return render(
        request,
        "saude/especialidade_list.html",
        {
            "q": q,
            "page_obj": page_obj,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "action_url": reverse("saude:especialidade_list"),
            "clear_url": reverse("saude:especialidade_list"),
            "has_filters": bool(q),
        },
    )


@login_required
@require_perm("saude.manage")
def especialidade_create(request):
    if request.method == "POST":
        form = EspecialidadeSaudeForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Especialidade cadastrada com sucesso.")
            return redirect("saude:especialidade_detail", obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = EspecialidadeSaudeForm()

    return render(
        request,
        "saude/especialidade_form.html",
        {
            "form": form,
            "mode": "create",
            "cancel_url": reverse("saude:especialidade_list"),
            "submit_label": "Salvar",
            "action_url": reverse("saude:especialidade_create"),
        },
    )


@login_required
@require_perm("saude.manage")
def especialidade_update(request, pk: int):
    obj = get_object_or_404(EspecialidadeSaude, pk=pk)

    if request.method == "POST":
        form = EspecialidadeSaudeForm(request.POST, instance=obj)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Especialidade atualizada com sucesso.")
            return redirect("saude:especialidade_detail", obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = EspecialidadeSaudeForm(instance=obj)

    return render(
        request,
        "saude/especialidade_form.html",
        {
            "form": form,
            "mode": "update",
            "obj": obj,
            "cancel_url": reverse("saude:especialidade_detail", args=[obj.pk]),
            "submit_label": "Salvar",
            "action_url": reverse("saude:especialidade_update", args=[obj.pk]),
        },
    )


@login_required
@require_perm("saude.view")
def especialidade_detail(request, pk: int):
    obj = get_object_or_404(EspecialidadeSaude, pk=pk)

    actions = [{"label": "Voltar", "url": reverse("saude:especialidade_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if can(request.user, "saude.manage"):
        actions.append({"label": "Editar", "url": reverse("saude:especialidade_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})

    fields = [
        {"label": "CBO", "value": obj.cbo or "—"},
    ]
    pills = [{"label": "Status", "value": "Ativo" if obj.ativo else "Inativo", "variant": "success" if obj.ativo else "danger"}]

    return render(request, "saude/especialidade_detail.html", {"obj": obj, "fields": fields, "pills": pills, "actions": actions})
