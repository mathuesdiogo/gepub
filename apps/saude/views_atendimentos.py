from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import can, scope_filter_unidades
from apps.core.exports import export_csv, export_pdf_table

from apps.org.models import Unidade
from .models import (
    ProfissionalSaude,
    AtendimentoSaude,
    AuditoriaAcessoProntuarioSaude,
)
from .forms import AtendimentoSaudeForm


@login_required
@require_perm("saude.view")
def atendimento_list(request):
    q = (request.GET.get("q") or "").strip()
    export = (request.GET.get("export") or "").strip().lower()

    unidades_qs = scope_filter_unidades(
        request.user,
        Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE)
    )

    qs = (
        AtendimentoSaude.objects.select_related("unidade", "profissional")
        .filter(unidade_id__in=unidades_qs.values_list("id", flat=True))
    )

    if q:
        qs = qs.filter(
            Q(paciente_nome__icontains=q)
            | Q(paciente_cpf__icontains=q)
            | Q(profissional__nome__icontains=q)
            | Q(unidade__nome__icontains=q)
        )

    qs = qs.order_by("-data", "-id")

    # =========================
    # EXPORTAÇÃO
    # =========================
    if export in ("csv", "pdf"):
        headers_export = ["Paciente", "CPF", "Data", "Tipo", "Profissional", "Unidade", "Observações"]
        rows_export = []
        for a in qs:
            rows_export.append([
                a.paciente_nome,
                a.paciente_cpf or "",
                a.data.strftime("%d/%m/%Y") if a.data else "",
                a.get_tipo_display(),
                getattr(a.profissional, "nome", "") or "",
                getattr(a.unidade, "nome", "") or "",
                (a.observacoes or "").strip(),
            ])

        if export == "csv":
            return export_csv("atendimentos_saude.csv", headers_export, rows_export)

        return export_pdf_table(
            request,
            filename="atendimentos_saude.pdf",
            title="Relatório — Atendimentos (Saúde)",
            headers=headers_export,
            rows=rows_export,
            filtros=f"Busca={q or '-'}",
        )

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    can_manage = can(request.user, "saude.manage")

    # mantém filtros na query
    base_q = f"q={q}" if q else ""
    join = "&" if base_q else ""
    actions = [
        {"label": "Exportar CSV", "url": f"?{base_q}{join}export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "Exportar PDF", "url": f"?{base_q}{join}export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]
    if can_manage:
        actions.append({"label": "Novo Atendimento", "url": reverse("saude:atendimento_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})

    headers = [
        {"label": "Paciente"},
        {"label": "Data", "width": "140px"},
        {"label": "Tipo", "width": "170px"},
        {"label": "Profissional"},
        {"label": "Unidade"},
    ]

    rows = []
    for a in page_obj:
        rows.append({
            "cells": [
                {"text": a.paciente_nome, "url": reverse("saude:atendimento_detail", args=[a.pk])},
                {"text": a.data.strftime("%d/%m/%Y") if a.data else "—"},
                {"text": a.get_tipo_display()},
                {"text": getattr(a.profissional, "nome", "—")},
                {"text": getattr(a.unidade, "nome", "—")},
            ],
            "can_edit": bool(can_manage),
            "edit_url": reverse("saude:atendimento_update", args=[a.pk]) if can_manage else "",
        })

    return render(request, "saude/atendimento_list.html", {
        "q": q,
        "page_obj": page_obj,
        "actions": actions,
        "headers": headers,
        "rows": rows,
        "action_url": reverse("saude:atendimento_list"),
        "clear_url": reverse("saude:atendimento_list"),
        "has_filters": bool(q),
    })


@login_required
@require_perm("saude.view")
def atendimento_detail(request, pk: int):
    unidades_qs = scope_filter_unidades(
        request.user,
        Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE)
    )

    qs = AtendimentoSaude.objects.select_related("unidade", "profissional").filter(
        unidade_id__in=unidades_qs.values_list("id", flat=True)
    )

    obj = get_object_or_404(qs, pk=pk)
    AuditoriaAcessoProntuarioSaude.objects.create(
        usuario=request.user,
        atendimento=obj,
        aluno=obj.aluno if obj.aluno_id else None,
        acao="VISUALIZACAO_ATENDIMENTO",
        ip=request.META.get("REMOTE_ADDR", ""),
    )

    can_manage = can(request.user, "saude.manage")

    actions = [{"label": "Voltar", "url": reverse("saude:atendimento_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if can_manage:
        actions.append({"label": "Editar", "url": reverse("saude:atendimento_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})
        actions.append({"label": "Documentos", "url": reverse("saude:documento_list", args=[obj.pk]), "icon": "fa-solid fa-file-medical", "variant": "btn--ghost"})
        actions.append({"label": "Prontuário", "url": reverse("saude:prontuario_hub", args=[obj.pk]), "icon": "fa-solid fa-notes-medical", "variant": "btn--ghost"})

    fields = [
        {"label": "Data", "value": obj.data.strftime("%d/%m/%Y") if obj.data else "—"},
        {"label": "Tipo", "value": obj.get_tipo_display()},
        {"label": "Profissional", "value": getattr(obj.profissional, "nome", "—")},
        {"label": "Unidade", "value": getattr(obj.unidade, "nome", "—")},
        {"label": "CPF do paciente", "value": obj.paciente_cpf or "—"},
        {"label": "Observações", "value": obj.observacoes or "—"},
        {"label": "Documentos clínicos", "value": str(obj.documentos_clinicos.count())},
    ]
    pills = [{"label": "Paciente", "value": obj.paciente_nome, "variant": "info"}]

    return render(request, "saude/atendimento_detail.html", {"obj": obj, "fields": fields, "pills": pills, "actions": actions})


@login_required
@require_perm("saude.manage")
def atendimento_create(request):
    unidades_qs = scope_filter_unidades(
        request.user,
        Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE).order_by("nome")
    )

    profissionais_qs = ProfissionalSaude.objects.filter(
        unidade_id__in=unidades_qs.values_list("id", flat=True),
        ativo=True,
    ).select_related("unidade").order_by("nome")

    if request.method == "POST":
        form = AtendimentoSaudeForm(request.POST, unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)
        if form.is_valid():
            obj = form.save(commit=False)

            if not unidades_qs.filter(pk=obj.unidade_id).exists():
                messages.error(request, "Unidade fora do seu escopo.")
                return redirect("saude:atendimento_create")

            if not profissionais_qs.filter(pk=obj.profissional_id).exists():
                messages.error(request, "Profissional fora do seu escopo.")
                return redirect("saude:atendimento_create")

            if obj.profissional.unidade_id != obj.unidade_id:
                messages.error(request, "O profissional selecionado não pertence à unidade escolhida.")
                return redirect("saude:atendimento_create")

            obj.save()
            messages.success(request, "Atendimento registrado com sucesso.")
            return redirect("saude:atendimento_detail", obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AtendimentoSaudeForm(unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)

    return render(request, "saude/atendimento_form.html", {"form": form, "mode": "create", "cancel_url": reverse("saude:atendimento_list")})


@login_required
@require_perm("saude.manage")
def atendimento_update(request, pk: int):
    unidades_qs = scope_filter_unidades(
        request.user,
        Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE).order_by("nome")
    )

    qs = AtendimentoSaude.objects.select_related("unidade", "profissional").filter(
        unidade_id__in=unidades_qs.values_list("id", flat=True)
    )
    obj = get_object_or_404(qs, pk=pk)

    profissionais_qs = ProfissionalSaude.objects.filter(
        unidade_id__in=unidades_qs.values_list("id", flat=True),
    ).select_related("unidade").order_by("nome")

    if request.method == "POST":
        form = AtendimentoSaudeForm(request.POST, instance=obj, unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)
        if form.is_valid():
            obj2 = form.save(commit=False)

            if not unidades_qs.filter(pk=obj2.unidade_id).exists():
                messages.error(request, "Unidade fora do seu escopo.")
                return redirect("saude:atendimento_update", pk=obj.pk)

            if not profissionais_qs.filter(pk=obj2.profissional_id).exists():
                messages.error(request, "Profissional fora do seu escopo.")
                return redirect("saude:atendimento_update", pk=obj.pk)

            if obj2.profissional.unidade_id != obj2.unidade_id:
                messages.error(request, "O profissional selecionado não pertence à unidade escolhida.")
                return redirect("saude:atendimento_update", pk=obj.pk)

            obj2.save()
            messages.success(request, "Atendimento atualizado com sucesso.")
            return redirect("saude:atendimento_detail", obj2.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AtendimentoSaudeForm(instance=obj, unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)

    return render(request, "saude/atendimento_form.html", {"form": form, "mode": "update", "cancel_url": reverse("saude:atendimento_detail", args=[obj.pk]), "obj": obj})
