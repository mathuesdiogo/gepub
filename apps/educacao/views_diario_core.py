from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.exports import export_pdf_table
from apps.core.rbac import scope_filter_turmas

from .forms_diario import AulaForm
from .forms_bncc import bncc_option_label
from .models import Turma, Matricula
from .models_diario import DiarioTurma, Aula
from .views_diario_permissions import can_edit_diario, can_view_diario, is_professor


def meus_diarios_impl(request):
    user = request.user
    is_prof = is_professor(user)

    if is_prof:
        qs = DiarioTurma.objects.select_related("turma", "turma__unidade").filter(professor=user).order_by("-ano_letivo", "turma__nome")
    else:
        turmas_scope = scope_filter_turmas(user, Turma.objects.all())
        qs = DiarioTurma.objects.select_related("turma", "turma__unidade", "professor").filter(turma__in=turmas_scope).order_by("-ano_letivo", "turma__nome", "professor__username")

    headers = [{"label": "Turma"}, {"label": "Unidade"}, {"label": "Ano", "width": "120px"}, {"label": "Professor", "width": "220px"}]
    rows = []

    for d in qs:
        rows.append(
            {
                "cells": [
                    {"text": d.turma.nome, "url": reverse("educacao:diario_detail", args=[d.pk])},
                    {"text": getattr(getattr(d.turma, "unidade", None), "nome", "—")},
                    {"text": str(d.ano_letivo)},
                    {"text": getattr(getattr(d, "professor", None), "username", "—")},
                ],
                "can_edit": False,
                "edit_url": "",
            }
        )

    return render(
        request,
        "educacao/diario_list.html",
        {
            "actions": [],
            "headers": headers,
            "rows": rows,
            "page_obj": None,
            "is_professor": is_prof,
        },
    )


def diario_detail_impl(request, pk: int):
    diario = get_object_or_404(
        DiarioTurma.objects.select_related("turma", "turma__unidade", "professor"),
        pk=pk,
    )

    if not can_view_diario(request.user, diario):
        return HttpResponseForbidden("403 — Você não tem permissão para acessar este diário.")

    can_edit = can_edit_diario(request.user, diario)

    export = (request.GET.get("export") or "").strip().lower()
    aulas = (
        diario.aulas.select_related("periodo", "componente")
        .prefetch_related("bncc_codigos")
        .order_by("-data", "-id")
    )

    if export == "pdf":
        headers = ["Data", "Período", "Componente", "Códigos BNCC", "Conteúdo", "Observações"]
        rows = []
        for a in aulas:
            codigos_txt = ", ".join([bncc_option_label(c, max_chars=64) for c in a.bncc_codigos.all()][:3])
            rows.append([
                a.data.strftime("%d/%m/%Y") if a.data else "—",
                str(a.periodo) if a.periodo else "—",
                str(a.componente) if a.componente else "—",
                codigos_txt or "—",
                (a.conteudo or "—")[:80],
                (a.observacoes or "—")[:80],
            ])

        filtros = f"Turma={diario.turma.nome} | Ano={diario.ano_letivo} | Professor={getattr(diario.professor, 'username', '-')}"
        return export_pdf_table(
            request,
            filename="diario_turma.pdf",
            title="Diário de Classe — Aulas",
            headers=headers,
            rows=rows,
            filtros=filtros,
        )

    actions = [
        {
            "label": "Voltar",
            "url": reverse("educacao:meus_diarios"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        },
        {
            "label": "Imprimir PDF",
            "url": reverse("educacao:diario_detail", args=[diario.pk]) + "?export=pdf",
            "icon": "fa-solid fa-file-pdf",
            "variant": "btn--ghost",
        },
        {
            "label": "Avaliações",
            "url": reverse("educacao:avaliacao_list", args=[diario.pk]),
            "icon": "fa-solid fa-clipboard-check",
            "variant": "btn--ghost",
        },
    ]

    if can_edit:
        actions.append(
            {
                "label": "Nova Aula",
                "url": reverse("educacao:aula_create", args=[diario.pk]),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            }
        )

    headers = [
        {"label": "Data", "width": "140px"},
        {"label": "Período", "width": "200px"},
        {"label": "Componente", "width": "180px"},
        {"label": "BNCC", "width": "220px"},
        {"label": "Conteúdo"},
        {"label": "Ações", "width": "220px"},
    ]

    rows = []
    for a in aulas:
        codigos = [bncc_option_label(c, max_chars=46) for c in a.bncc_codigos.all()]
        rows.append(
            {
                "cells": [
                    {"text": a.data.strftime("%d/%m/%Y") if a.data else "—", "url": ""},
                    {"text": str(a.periodo) if a.periodo else "—"},
                    {"text": str(a.componente) if a.componente else "—"},
                    {"text": ", ".join(codigos[:2]) if codigos else "—"},
                    {"text": (a.conteudo or "—")[:120]},
                    {"text": "Frequência", "url": reverse("educacao:aula_frequencia", args=[diario.pk, a.pk])},
                ],
                "can_edit": False,
                "edit_url": "",
            }
        )

    return render(
        request,
        "educacao/diario_detail.html",
        {
            "diario": diario,
            "can_edit": can_edit,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "page_obj": None,
        },
    )


def aula_create_impl(request, pk: int):
    diario = get_object_or_404(DiarioTurma.objects.select_related("turma", "professor"), pk=pk)

    if not can_edit_diario(request.user, diario):
        return HttpResponseForbidden("403 — Somente o professor responsável pode criar aula.")

    if request.method == "POST":
        form = AulaForm(request.POST, diario=diario)
        if form.is_valid():
            aula = form.save(commit=False)
            aula.diario = diario
            aula.save()
            form.save_m2m()
            messages.success(request, "Aula criada com sucesso.")
            return redirect("educacao:diario_detail", pk=diario.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AulaForm(diario=diario)

    return render(
        request,
        "educacao/aula_form.html",
        {
            "form": form,
            "diario": diario,
            "mode": "create",
            "cancel_url": reverse("educacao:diario_detail", args=[diario.pk]),
            "submit_label": "Salvar",
            "action_url": reverse("educacao:aula_create", args=[diario.pk]),
            "bncc_hint": getattr(form, "bncc_hint", ""),
        },
    )


def aula_update_impl(request, pk: int, aula_id: int):
    diario = get_object_or_404(
        DiarioTurma.objects.select_related("turma", "professor"),
        pk=pk,
    )

    if not can_edit_diario(request.user, diario):
        return HttpResponseForbidden("403 — Somente o professor responsável pode editar esta aula.")

    aula = get_object_or_404(Aula, pk=aula_id, diario=diario)

    if request.method == "POST":
        form = AulaForm(request.POST, instance=aula, diario=diario)
        if form.is_valid():
            form.save()
            messages.success(request, "Aula atualizada com sucesso.")
            return redirect("educacao:diario_detail", pk=diario.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AulaForm(instance=aula, diario=diario)

    return render(
        request,
        "educacao/aula_form.html",
        {
            "form": form,
            "diario": diario,
            "aula": aula,
            "mode": "update",
            "cancel_url": reverse("educacao:diario_detail", args=[diario.pk]),
            "submit_label": "Atualizar",
            "action_url": reverse("educacao:aula_update", args=[diario.pk, aula.pk]),
            "bncc_hint": getattr(form, "bncc_hint", ""),
        },
    )


def diario_create_for_turma_impl(request, pk: int):
    turma_qs = scope_filter_turmas(request.user, Turma.objects.select_related("unidade"))
    turma = get_object_or_404(turma_qs, pk=pk)

    if getattr(getattr(request.user, "profile", None), "role", "") != "PROFESSOR":
        return HttpResponseForbidden("403 — Somente professor pode criar diário.")

    diario, _created = DiarioTurma.objects.get_or_create(
        turma=turma,
        professor=request.user,
        ano_letivo=getattr(turma, "ano_letivo", None) or timezone.localdate().year,
    )
    return redirect("educacao:diario_detail", pk=diario.pk)


def diario_turma_entry_impl(request, pk: int):
    turma_qs = scope_filter_turmas(
        request.user,
        Turma.objects.select_related("unidade", "unidade__secretaria", "unidade__secretaria__municipio"),
    )
    turma = get_object_or_404(turma_qs, pk=pk)

    if is_professor(request.user):
        diario, _created = DiarioTurma.objects.get_or_create(
            turma=turma,
            professor=request.user,
            ano_letivo=getattr(turma, "ano_letivo", None) or timezone.localdate().year,
        )
        return redirect("educacao:diario_detail", pk=diario.pk)

    diarios = (
        DiarioTurma.objects.select_related("turma", "turma__unidade", "professor")
        .filter(turma=turma)
        .order_by("-ano_letivo", "professor__username")
    )

    if diarios.count() == 1:
        return redirect("educacao:diario_detail", pk=diarios.first().pk)

    headers = [
        {"label": "Ano", "width": "120px"},
        {"label": "Professor"},
        {"label": "Unidade"},
    ]
    rows = []
    for d in diarios:
        rows.append(
            {
                "cells": [
                    {"text": str(d.ano_letivo), "url": reverse("educacao:diario_detail", args=[d.pk])},
                    {"text": getattr(getattr(d, "professor", None), "username", "—")},
                    {"text": getattr(getattr(getattr(d, "turma", None), "unidade", None), "nome", "—")},
                ],
                "can_edit": False,
                "edit_url": "",
            }
        )

    actions = [
        {
            "label": "Voltar",
            "url": reverse("educacao:turma_detail", args=[turma.pk]),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        },
    ]

    return render(
        request,
        "educacao/diario_turma_select.html",
        {
            "turma": turma,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "page_obj": None,
        },
    )
