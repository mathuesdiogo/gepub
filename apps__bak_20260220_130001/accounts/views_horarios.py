from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.decorators import require_perm
from apps.core.exports import export_pdf_table
from apps.core.rbac import can, scope_filter_turmas

from .models import Turma
from .models_horarios import GradeHorario, AulaHorario


@login_required
@require_perm("educacao.view")
def horario_turma(request, pk: int):
    turma_qs = scope_filter_turmas(
        request.user,
        Turma.objects.select_related("unidade", "unidade__secretaria", "unidade__secretaria__municipio"),
    )
    turma = get_object_or_404(turma_qs, pk=pk)

    grade, _ = GradeHorario.objects.get_or_create(turma=turma)

    can_edit = can(request.user, "educacao.manage")

    export = (request.GET.get("export") or "").strip().lower()
    aulas = grade.aulas.select_related("professor").all()

    if export == "pdf":
        headers = ["Dia", "Início", "Fim", "Disciplina", "Professor", "Sala"]
        rows = []
        for a in aulas:
            rows.append([
                a.get_dia_display(),
                a.inicio.strftime("%H:%M") if a.inicio else "—",
                a.fim.strftime("%H:%M") if a.fim else "—",
                a.disciplina,
                getattr(getattr(a, "professor", None), "username", "—"),
                a.sala or "—",
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
        {"label": "Voltar", "url": reverse("educacao:turma_detail", args=[turma.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Imprimir PDF", "url": reverse("educacao:horario_turma", args=[turma.pk]) + "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]
    if can_edit:
        actions.append({"label": "Adicionar Aula", "url": reverse("educacao:horario_aula_create", args=[turma.pk]), "icon": "fa-solid fa-plus", "variant": "btn-primary"})

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
        rows.append({
            "cells": [
                {"text": a.get_dia_display()},
                {"text": a.inicio.strftime("%H:%M") if a.inicio else "—"},
                {"text": a.fim.strftime("%H:%M") if a.fim else "—"},
                {"text": a.disciplina},
                {"text": getattr(getattr(a, "professor", None), "username", "—")},
                {"text": a.sala or "—"},
            ],
            "can_edit": bool(can_edit),
            "edit_url": reverse("educacao:horario_aula_update", args=[turma.pk, a.pk]) if can_edit else "",
        })

    return render(request, "educacao/horario_turma.html", {
        "turma": turma,
        "grade": grade,
        "actions": actions,
        "headers": headers,
        "rows": rows,
        "page_obj": None,
        "can_edit": can_edit,
    })


@login_required
@require_perm("educacao.view")
def horario_aula_create(request, pk: int):
    if not can(request.user, "educacao.manage"):
        return HttpResponseForbidden("403 — Você não tem permissão para editar horários.")

    turma_qs = scope_filter_turmas(request.user, Turma.objects.all())
    turma = get_object_or_404(turma_qs, pk=pk)
    grade, _ = GradeHorario.objects.get_or_create(turma=turma)

    if request.method == "POST":
        dia = (request.POST.get("dia") or "").strip()
        inicio = (request.POST.get("inicio") or "").strip()
        fim = (request.POST.get("fim") or "").strip()
        disciplina = (request.POST.get("disciplina") or "").strip()
        sala = (request.POST.get("sala") or "").strip()

        if not (dia and inicio and fim and disciplina):
            messages.error(request, "Preencha dia, início, fim e disciplina.")
        else:
            AulaHorario.objects.create(
                grade=grade,
                dia=dia,
                inicio=inicio,
                fim=fim,
                disciplina=disciplina,
                sala=sala,
            )
            messages.success(request, "Aula adicionada ao horário.")
            return redirect("educacao:horario_turma", pk=turma.pk)

    return render(request, "educacao/horario_aula_form.html", {
        "turma": turma,
        "mode": "create",
        "cancel_url": reverse("educacao:horario_turma", args=[turma.pk]),
        "action_url": reverse("educacao:horario_aula_create", args=[turma.pk]),
        "submit_label": "Salvar",
        "dias": AulaHorario.Dia.choices,
    })


@login_required
@require_perm("educacao.view")
def horario_aula_update(request, pk: int, aula_id: int):
    if not can(request.user, "educacao.manage"):
        return HttpResponseForbidden("403 — Você não tem permissão para editar horários.")

    turma_qs = scope_filter_turmas(request.user, Turma.objects.all())
    turma = get_object_or_404(turma_qs, pk=pk)
    grade = get_object_or_404(GradeHorario, turma=turma)
    aula = get_object_or_404(AulaHorario, grade=grade, pk=aula_id)

    if request.method == "POST":
        aula.dia = (request.POST.get("dia") or aula.dia).strip()
        aula.inicio = (request.POST.get("inicio") or aula.inicio)
        aula.fim = (request.POST.get("fim") or aula.fim)
        aula.disciplina = (request.POST.get("disciplina") or aula.disciplina).strip()
        aula.sala = (request.POST.get("sala") or aula.sala).strip()
        aula.save()
        messages.success(request, "Horário atualizado.")
        return redirect("educacao:horario_turma", pk=turma.pk)

    return render(request, "educacao/horario_aula_form.html", {
        "turma": turma,
        "mode": "update",
        "aula": aula,
        "cancel_url": reverse("educacao:horario_turma", args=[turma.pk]),
        "action_url": reverse("educacao:horario_aula_update", args=[turma.pk, aula.pk]),
        "submit_label": "Atualizar",
        "dias": AulaHorario.Dia.choices,
    })
