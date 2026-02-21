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

from apps.core.exports import export_csv, export_pdf_table




@login_required
@require_perm("saude.view")
def unidade_list(request):
    q = (request.GET.get("q") or "").strip()
    export = (request.GET.get("export") or "").strip().lower()

    qs = Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE).order_by("nome")
    qs = scope_filter_unidades(request.user, qs)

    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(codigo_inep__icontains=q)
            | Q(cnpj__icontains=q)
            | Q(endereco__icontains=q)
            | Q(telefone__icontains=q)
        )

    # =========================
    # EXPORTAÇÃO
    # =========================
    if export in ("csv", "pdf"):
        headers_export = ["Nome", "INEP", "CNPJ", "Telefone", "E-mail", "Ativo"]
        rows_export = []
        for u in qs:
            rows_export.append([
                u.nome,
                u.codigo_inep or "",
                u.cnpj or "",
                u.telefone or "",
                u.email or "",
                "Sim" if u.ativo else "Não",
            ])

        if export == "csv":
            return export_csv("unidades_saude.csv", headers_export, rows_export)

        filtros_txt = f"Busca={q or '-'}"
        return export_pdf_table(
            request,
            filename="unidades_saude.pdf",
            title="Relatório — Unidades de Saúde",
            headers=headers_export,
            rows=rows_export,
            filtros=filtros_txt,
        )

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    can_manage = can(request.user, "saude.manage")

    base_q = []
    if q:
        base_q.append(f"q={q}")
    base_query = "&".join(base_q)

    def qjoin(extra: str) -> str:
        return f"?{base_query + ('&' if base_query else '')}{extra}"

    actions = [
        {"label": "Exportar CSV", "url": qjoin("export=csv"), "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "Exportar PDF", "url": qjoin("export=pdf"), "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]
    if can_manage:
        actions.append({"label": "Nova Unidade", "url": reverse("saude:unidade_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})

    headers = [
        {"label": "Unidade"},
        {"label": "INEP", "width": "140px"},
        {"label": "Telefone", "width": "160px"},
        {"label": "Ativo", "width": "120px"},
    ]

    rows = []
    for u in page_obj:
        rows.append({
            "cells": [
                {"text": u.nome, "url": reverse("saude:unidade_detail", args=[u.pk])},
                {"text": u.codigo_inep or "—"},
                {"text": u.telefone or "—"},
                {"text": "Sim" if u.ativo else "Não"},
            ],
            "can_edit": bool(can_manage),
            "edit_url": reverse("saude:unidade_update", args=[u.pk]) if can_manage else "",
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
        "autocomplete_url": reverse("saude:api_unidades_suggest"),
        "autocomplete_href": reverse("saude:unidade_list") + "?q={q}",
    })



@login_required
@require_perm("saude.view")
def api_unidades_suggest(request):
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    qs = Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE).order_by("nome")
    qs = scope_filter_unidades(request.user, qs)

    qs = qs.filter(Q(nome__icontains=q) | Q(codigo__icontains=q)).order_by("nome")[:10]

    results = [{"id": u.id, "text": u.nome, "meta": getattr(u, "codigo", "") or ""} for u in qs]
    return JsonResponse({"results": results})

@login_required
@require_perm("saude.view")
def unidade_detail(request, pk: int):
    qs = (
        Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE)
        .select_related("secretaria", "secretaria__municipio")
    )
    qs = scope_filter_unidades(request.user, qs)
    unidade = get_object_or_404(qs, pk=pk)

    can_manage = can(request.user, "saude.manage")

    actions = [{"label": "Voltar", "url": reverse("saude:unidade_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if can_manage:
        actions.append({"label": "Editar", "url": reverse("saude:unidade_update", args=[unidade.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})

    fields = [
        {"label": "Secretaria", "value": getattr(unidade.secretaria, "nome", "—")},
        {"label": "Município", "value": getattr(getattr(unidade.secretaria, "municipio", None), "nome", "—")},
        {"label": "Telefone", "value": getattr(unidade, "telefone", "") or "—"},
        {"label": "E-mail", "value": getattr(unidade, "email", "") or "—"},
        {"label": "Endereço", "value": getattr(unidade, "endereco", "") or "—"},
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
