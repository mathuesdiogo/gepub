from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import can
from apps.core.exports import export_csv, export_pdf_table

from .models import ProfissionalSaude
from .forms import ProfissionalSaudeForm


@login_required
@require_perm("saude.view")
def profissional_list(request):
    q = (request.GET.get("q") or "").strip()
    export = (request.GET.get("export") or "").strip().lower()

    qs = ProfissionalSaude.objects.select_related("unidade").order_by("nome")

    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(cpf__icontains=q)
            | Q(email__icontains=q)
            | Q(telefone__icontains=q)
            | Q(unidade__nome__icontains=q)
            | Q(cargo__icontains=q)
        )

    # =========================
    # EXPORTAÇÃO (respeita filtros)
    # =========================
    if export in ("csv", "pdf"):
        headers_export = ["Nome", "Unidade", "Especialidade", "Cargo", "CPF", "Telefone", "E-mail", "Ativo"]
        rows_export = []
        for p in qs:
            rows_export.append([
                p.nome,
                p.unidade.nome if p.unidade else "",
                p.especialidade.nome if getattr(p, "especialidade", None) else "",
                p.get_cargo_display(),
                p.cpf or "",
                p.telefone or "",
                p.email or "",
                "Sim" if p.ativo else "Não",
            ])

        if export == "csv":
            return export_csv("profissionais_saude.csv", headers_export, rows_export)

        filtros_txt = f"Busca={q or '-'}"
        return export_pdf_table(
            request,
            filename="profissionais_saude.pdf",
            title="Relatório — Profissionais de Saúde",
            headers=headers_export,
            rows=rows_export,
            filtros=filtros_txt,
        )

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    can_manage = can(request.user, "saude.manage")

    # mantém filtros na query do export
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
        actions.append({"label": "Novo Profissional", "url": reverse("saude:profissional_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})

    headers = [
        {"label": "Nome"},
        {"label": "Unidade"},
        {"label": "Especialidade"},
        {"label": "Cargo"},
        {"label": "Ativo", "width": "120px"},
    ]

    rows = []
    for p in page_obj:
        rows.append({
            "cells": [
                {"text": p.nome, "url": reverse("saude:profissional_detail", args=[p.pk])},
                {"text": p.unidade.nome if p.unidade else "—"},
                {"text": p.especialidade.nome if getattr(p, "especialidade", None) else "—"},
                {"text": p.get_cargo_display()},
                {"text": "Sim" if p.ativo else "Não"},
            ],
            "can_edit": bool(can_manage),
            "edit_url": reverse("saude:profissional_update", args=[p.pk]) if can_manage else "",
        })

    return render(
        request,
        "saude/profissional_list.html",
        {
            "q": q,
            "page_obj": page_obj,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "action_url": reverse("saude:profissional_list"),
            "clear_url": reverse("saude:profissional_list"),
            "has_filters": bool(q),
            "autocomplete_url": reverse("saude:api_profissionais_suggest"),
            "autocomplete_href": reverse("saude:profissional_list") + "?q={q}",
        },
    )


@login_required
@require_perm("saude.manage")
def profissional_create(request):
    if request.method == "POST":
        form = ProfissionalSaudeForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Profissional cadastrado com sucesso.")
            return redirect("saude:profissional_detail", obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = ProfissionalSaudeForm()

    return render(
        request,
        "saude/profissional_form.html",
        {
            "form": form,
            "mode": "create",
            "cancel_url": reverse("saude:profissional_list"),
            "submit_label": "Salvar",
            "action_url": reverse("saude:profissional_create"),
        },
    )


@login_required
@require_perm("saude.manage")
def profissional_update(request, pk: int):
    obj = get_object_or_404(ProfissionalSaude.objects.select_related("unidade"), pk=pk)

    if request.method == "POST":
        form = ProfissionalSaudeForm(request.POST, instance=obj)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Profissional atualizado com sucesso.")
            return redirect("saude:profissional_detail", obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = ProfissionalSaudeForm(instance=obj)

    return render(
        request,
        "saude/profissional_form.html",
        {
            "form": form,
            "mode": "update",
            "obj": obj,
            "cancel_url": reverse("saude:profissional_detail", args=[obj.pk]),
            "submit_label": "Salvar",
            "action_url": reverse("saude:profissional_update", args=[obj.pk]),
        },
    )


@login_required
@require_perm("saude.view")
def profissional_detail(request, pk: int):
    obj = get_object_or_404(ProfissionalSaude.objects.select_related("unidade"), pk=pk)

    actions = [{"label": "Voltar", "url": reverse("saude:profissional_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if can(request.user, "saude.manage"):
        actions.append({"label": "Editar", "url": reverse("saude:profissional_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})

    fields = [
        {"label": "Unidade", "value": obj.unidade.nome if obj.unidade else "—"},
        {"label": "Especialidade", "value": obj.especialidade.nome if getattr(obj, "especialidade", None) else "—"},
        {"label": "Cargo", "value": obj.get_cargo_display()},
        {"label": "Conselho", "value": obj.conselho_numero or "—"},
        {"label": "CBO", "value": obj.cbo or "—"},
        {"label": "Carga horária semanal", "value": obj.carga_horaria_semanal},
        {"label": "CPF", "value": obj.cpf or "—"},
        {"label": "Telefone", "value": obj.telefone or "—"},
        {"label": "E-mail", "value": obj.email or "—"},
    ]
    pills = [{"label": "Status", "value": "Ativo" if obj.ativo else "Inativo", "variant": "success" if obj.ativo else "danger"}]

    return render(request, "saude/profissional_detail.html", {"obj": obj, "fields": fields, "pills": pills, "actions": actions})


# =========================
# AUTOCOMPLETE (API)
# =========================
@login_required
@require_perm("saude.view")
def api_profissionais_suggest(request):
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    qs = (
        ProfissionalSaude.objects.select_related("unidade")
        .filter(Q(nome__icontains=q) | Q(cpf__icontains=q) | Q(unidade__nome__icontains=q))
        .order_by("nome")[:10]
    )

    results = []
    for p in qs:
        results.append({
            "id": p.id,
            "text": p.nome,
            "meta": p.unidade.nome if p.unidade else "",
        })

    return JsonResponse({"results": results})
