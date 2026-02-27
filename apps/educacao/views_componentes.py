from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.exports import export_csv, export_pdf_table
from apps.core.rbac import can

from .forms_bncc import bncc_option_label
from .forms_componentes import ComponenteCurricularForm
from .models_notas import BNCCCodigo, ComponenteCurricular


@login_required
@require_perm("educacao.view")
def componente_list(request):
    q = (request.GET.get("q") or "").strip()

    qs = ComponenteCurricular.objects.annotate(total_bncc=Count("bncc_codigos", distinct=True)).order_by("nome")
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(sigla__icontains=q))

    export = (request.GET.get("export") or "").strip().lower()
    if export in {"csv", "pdf"}:
        headers = ["Nome", "Sigla", "Modalidade BNCC", "Etapa BNCC", "Área", "Códigos BNCC", "Ativo"]
        rows = [
            [
                c.nome or "",
                c.sigla or "",
                c.get_modalidade_bncc_display() if c.modalidade_bncc else "—",
                c.get_etapa_bncc_display() if c.etapa_bncc else "—",
                c.area_codigo_bncc or "—",
                str(getattr(c, "total_bncc", 0)),
                "Sim" if c.ativo else "Não",
            ]
            for c in qs
        ]
        if export == "csv":
            return export_csv("componentes_curriculares.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="componentes_curriculares.pdf",
            title="Componentes Curriculares",
            headers=headers,
            rows=rows,
            filtros=f"Busca={q or '-'}",
        )

    page_obj = Paginator(qs, 12).get_page(request.GET.get("page"))
    can_manage = can(request.user, "educacao.manage")

    base_q = f"q={q}" if q else ""
    actions = [
        {"label": "Exportar CSV", "url": f"?{base_q + ('&' if base_q else '')}export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "Exportar PDF", "url": f"?{base_q + ('&' if base_q else '')}export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]
    if can_manage:
        actions.append(
            {"label": "Novo Componente", "url": reverse("educacao:componente_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"}
        )

    headers = [
        {"label": "Nome"},
        {"label": "Sigla", "width": "140px"},
        {"label": "Modalidade", "width": "170px"},
        {"label": "Etapa", "width": "220px"},
        {"label": "Área", "width": "100px"},
        {"label": "BNCC", "width": "100px"},
        {"label": "Ativo", "width": "120px"},
    ]
    rows = []
    for c in page_obj:
        rows.append(
            {
                "cells": [
                    {"text": c.nome, "url": reverse("educacao:componente_detail", args=[c.pk])},
                    {"text": c.sigla or "—"},
                    {"text": c.get_modalidade_bncc_display() if c.modalidade_bncc else "—"},
                    {"text": c.get_etapa_bncc_display() if c.etapa_bncc else "—"},
                    {"text": c.area_codigo_bncc or "—"},
                    {"text": str(getattr(c, "total_bncc", 0))},
                    {"text": "Sim" if c.ativo else "Não"},
                ],
                "can_edit": bool(can_manage),
                "edit_url": reverse("educacao:componente_update", args=[c.pk]) if can_manage else "",
            }
        )

    return render(
        request,
        "educacao/componente_list.html",
        {
            "q": q,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "page_obj": page_obj,
            "action_url": reverse("educacao:componente_list"),
            "clear_url": reverse("educacao:componente_list"),
        },
    )


@login_required
@require_perm("educacao.view")
def componente_detail(request, pk: int):
    componente = get_object_or_404(ComponenteCurricular, pk=pk)
    can_manage = can(request.user, "educacao.manage")

    referencia_label = "—"
    if componente.codigo_bncc_referencia:
        referencia_codigo = componente.codigo_bncc_referencia.strip().upper()
        referencia_obj = (
            componente.bncc_codigos.filter(codigo=referencia_codigo, ativo=True).first()
            or BNCCCodigo.objects.filter(codigo=referencia_codigo, ativo=True).first()
        )
        referencia_label = bncc_option_label(referencia_obj) if referencia_obj else referencia_codigo

    actions = [
        {"label": "Voltar", "url": reverse("educacao:componente_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
    ]
    if can_manage:
        actions.append({"label": "Editar", "url": reverse("educacao:componente_update", args=[componente.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})

    fields = [
        {"label": "Nome", "value": componente.nome},
        {"label": "Sigla", "value": componente.sigla or "—"},
        {"label": "Modalidade BNCC", "value": componente.get_modalidade_bncc_display() if componente.modalidade_bncc else "—"},
        {"label": "Etapa BNCC", "value": componente.get_etapa_bncc_display() if componente.etapa_bncc else "—"},
        {"label": "Área BNCC", "value": componente.area_codigo_bncc or "—"},
        {"label": "Código referência", "value": referencia_label},
        {"label": "Ativo", "value": "Sim" if componente.ativo else "Não"},
    ]
    pills = [
        {"label": "Avaliações curriculares", "value": componente.avaliacoes_notas.count()},
    ]

    return render(
        request,
        "educacao/componente_detail.html",
        {
            "componente": componente,
            "actions": actions,
            "fields": fields,
            "pills": pills,
        },
    )


@login_required
@require_perm("educacao.manage")
def componente_create(request):
    if request.method == "POST":
        form = ComponenteCurricularForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Componente curricular criado com sucesso.")
            return redirect("educacao:componente_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = ComponenteCurricularForm()

    return render(
        request,
        "educacao/componente_form.html",
        {
            "form": form,
            "mode": "create",
            "bncc_total": getattr(form, "bncc_options_total", 0),
            "cancel_url": reverse("educacao:componente_list"),
            "submit_label": "Salvar",
            "action_url": reverse("educacao:componente_create"),
        },
    )


@login_required
@require_perm("educacao.manage")
def componente_update(request, pk: int):
    componente = get_object_or_404(ComponenteCurricular, pk=pk)
    if request.method == "POST":
        form = ComponenteCurricularForm(request.POST, instance=componente)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Componente curricular atualizado com sucesso.")
            return redirect("educacao:componente_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = ComponenteCurricularForm(instance=componente)

    return render(
        request,
        "educacao/componente_form.html",
        {
            "form": form,
            "mode": "update",
            "componente": componente,
            "bncc_total": getattr(form, "bncc_options_total", 0),
            "cancel_url": reverse("educacao:componente_list"),
            "submit_label": "Atualizar",
            "action_url": reverse("educacao:componente_update", args=[componente.pk]),
        },
    )
