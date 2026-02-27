from datetime import time

from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.exports import export_pdf_table
from apps.core.rbac import can, scope_filter_turmas

from .forms_horarios import AulaHorarioForm
from .models import Turma
from .models_horarios import GradeHorario, AulaHorario


def parse_hhmm(value: str):
    value = (value or "").strip()
    if not value:
        return None
    parts = value.split(":")
    if len(parts) != 2:
        return None
    try:
        hh = int(parts[0])
        mm = int(parts[1])
    except ValueError:
        return None
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        return None
    return time(hh, mm)


def can_edit_horario(user, turma: Turma) -> bool:
    if can(user, "educacao.manage"):
        return True

    prof = getattr(user, "profile", None)
    if prof and getattr(prof, "role", None) == "PROFESSOR":
        if hasattr(prof, "unidade_id") and prof.unidade_id == turma.unidade_id:
            return True

    return False


def horario_turma_impl(request, turma_id: int):
    turma_qs = scope_filter_turmas(
        request.user,
        Turma.objects.select_related(
            "unidade",
            "unidade__secretaria",
            "unidade__secretaria__municipio",
        ),
    )
    turma = get_object_or_404(turma_qs, pk=turma_id)

    grade, _ = GradeHorario.objects.get_or_create(turma=turma)
    can_edit = can_edit_horario(request.user, turma)

    export = (request.GET.get("export") or "").strip().lower()
    aulas = grade.aulas.select_related("professor").all()

    if export == "pdf":
        headers = ["Dia", "Início", "Fim", "Disciplina", "Professor", "Sala"]
        rows = []
        for a in aulas:
            rows.append([
                a.get_dia_display(),
                a.inicio.strftime("%H:%M") if getattr(a, "inicio", None) else "—",
                a.fim.strftime("%H:%M") if getattr(a, "fim", None) else "—",
                getattr(a, "disciplina", "") or "—",
                getattr(getattr(a, "professor", None), "username", "—"),
                getattr(a, "sala", "") or "—",
            ])

        filtros = f"Turma={turma.nome} | Ano={turma.ano_letivo} | Unidade={getattr(turma.unidade, 'nome', '-')}"
        return export_pdf_table(
            request,
            filename="horario_turma.pdf",
            title="Horário da Turma",
            headers=headers,
            rows=rows,
            filtros=filtros,
        )

    actions = [
        {
            "label": "Voltar",
            "url": reverse("educacao:horarios_index"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        },
        {
            "label": "Imprimir PDF",
            "url": reverse("educacao:horario_turma", args=[turma.pk]) + "?export=pdf",
            "icon": "fa-solid fa-file-pdf",
            "variant": "btn--ghost",
        },
    ]

    if can_edit:
        actions.extend(
            [
                {
                    "label": "Gerar Padrão",
                    "url": reverse("educacao:horario_gerar_padrao", args=[turma.pk]),
                    "icon": "fa-solid fa-wand-magic-sparkles",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Duplicar horário",
                    "url": reverse("educacao:horario_duplicar_select", args=[turma.pk]),
                    "icon": "fa-solid fa-copy",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Limpar horário",
                    "url": reverse("educacao:horario_limpar", args=[turma.pk]),
                    "icon": "fa-solid fa-trash",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Adicionar Aula",
                    "url": reverse("educacao:horario_aula_create", args=[turma.pk]),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
            ]
        )

    headers = [
        {"label": "Dia", "width": "140px"},
        {"label": "Início", "width": "110px"},
        {"label": "Fim", "width": "110px"},
        {"label": "Disciplina"},
        {"label": "Professor", "width": "220px"},
        {"label": "Sala", "width": "140px"},
    ]

    rows = []
    for a in aulas:
        rows.append(
            {
                "cells": [
                    {"text": a.get_dia_display()},
                    {"text": a.inicio.strftime("%H:%M") if getattr(a, "inicio", None) else "—"},
                    {"text": a.fim.strftime("%H:%M") if getattr(a, "fim", None) else "—"},
                    {"text": getattr(a, "disciplina", "") or "—"},
                    {"text": getattr(getattr(a, "professor", None), "username", "—")},
                    {"text": getattr(a, "sala", "") or "—"},
                ],
                "can_edit": bool(can_edit),
                "edit_url": reverse("educacao:horario_aula_update", args=[turma.pk, a.pk]) if can_edit else "",
            }
        )

    return render(
        request,
        "educacao/horario_turma.html",
        {
            "turma": turma,
            "grade": grade,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "page_obj": None,
            "can_edit": can_edit,
        },
    )


def horario_aula_create_impl(request, turma_id: int):
    turma_qs = scope_filter_turmas(request.user, Turma.objects.all())
    turma = get_object_or_404(turma_qs, pk=turma_id)

    if not can_edit_horario(request.user, turma):
        return HttpResponseForbidden("403 — Você não tem permissão para editar horários.")

    grade, _ = GradeHorario.objects.get_or_create(turma=turma)

    if request.method == "POST":
        form = AulaHorarioForm(request.POST, grade=grade)
        if form.is_valid():
            aula = form.save(commit=False)
            aula.grade = grade
            aula.save()
            messages.success(request, "Aula adicionada ao horário.")
            return redirect("educacao:horario_turma", turma_id=turma.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AulaHorarioForm(grade=grade)

    return render(
        request,
        "educacao/horario_aula_form.html",
        {
            "turma": turma,
            "mode": "create",
            "form": form,
            "cancel_url": reverse("educacao:horario_turma", args=[turma.pk]),
            "action_url": reverse("educacao:horario_aula_create", args=[turma.pk]),
            "submit_label": "Salvar",
        },
    )


def horario_aula_update_impl(request, turma_id: int, aula_id: int):
    turma_qs = scope_filter_turmas(request.user, Turma.objects.all())
    turma = get_object_or_404(turma_qs, pk=turma_id)

    if not can_edit_horario(request.user, turma):
        return HttpResponseForbidden("403 — Você não tem permissão para editar horários.")

    grade = get_object_or_404(GradeHorario, turma=turma)
    aula = get_object_or_404(AulaHorario, grade=grade, pk=aula_id)

    if request.method == "POST":
        form = AulaHorarioForm(request.POST, instance=aula, grade=grade)
        if form.is_valid():
            form.save()
            messages.success(request, "Horário atualizado.")
            return redirect("educacao:horario_turma", turma_id=turma.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AulaHorarioForm(instance=aula, grade=grade)

    return render(
        request,
        "educacao/horario_aula_form.html",
        {
            "turma": turma,
            "mode": "update",
            "aula": aula,
            "form": form,
            "cancel_url": reverse("educacao:horario_turma", args=[turma.pk]),
            "action_url": reverse("educacao:horario_aula_update", args=[turma.pk, aula.pk]),
            "submit_label": "Atualizar",
        },
    )
