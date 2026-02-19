from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.exports import export_pdf_table
from apps.core.rbac import scope_filter_turmas

from .forms_notas import AvaliacaoForm
from .models import Turma, Matricula
from .models_diario import DiarioTurma, Aula, Avaliacao, Nota


def _is_professor(user) -> bool:
    return getattr(getattr(user, "profile", None), "role", "") == "PROFESSOR"


def _can_edit_diario(user, diario: DiarioTurma) -> bool:
    return _is_professor(user) and diario.professor_id == user.id


def _can_view_diario(user, diario: DiarioTurma) -> bool:
    if _can_edit_diario(user, diario):
        return True
    turmas_scope = scope_filter_turmas(user, Turma.objects.all()).values_list("id", flat=True)
    return diario.turma_id in set(turmas_scope)


@login_required
@require_perm("educacao.view")
def avaliacao_list(request, pk: int):
    diario = get_object_or_404(DiarioTurma.objects.select_related("turma", "professor", "turma__unidade"), pk=pk)

    if not _can_view_diario(request.user, diario):
        return HttpResponseForbidden("403 — Você não tem permissão para acessar este diário.")

    can_edit = _can_edit_diario(request.user, diario)

    export = (request.GET.get("export") or "").strip().lower()
    qs = diario.avaliacoes.all().order_by("-data", "-id")

    if export == "pdf":
        headers = ["Data", "Avaliação", "Peso"]
        rows = []
        for a in qs:
            rows.append([
                a.data.strftime("%d/%m/%Y") if a.data else "—",
                a.titulo,
                str(a.peso),
            ])
        filtros = f"Turma={diario.turma.nome} | Professor={getattr(diario.professor, 'username', '-')}"
        return export_pdf_table(
            request,
            filename="avaliacoes.pdf",
            title="Avaliações — Diário de Classe",
            headers=headers,
            rows=rows,
            filtros=filtros,
        )

    actions = [
        {"label": "Voltar", "url": reverse("educacao:diario_detail", args=[diario.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Imprimir PDF", "url": reverse("educacao:avaliacao_list", args=[diario.pk]) + "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]
    if can_edit:
        actions.append({"label": "Nova Avaliação", "url": reverse("educacao:avaliacao_create", args=[diario.pk]), "icon": "fa-solid fa-plus", "variant": "btn-primary"})

    headers = [{"label": "Data", "width": "140px"}, {"label": "Avaliação"}, {"label": "Peso", "width": "120px"}, {"label": "Lançar notas", "width": "160px"}]
    rows = []
    for a in qs:
        rows.append({
            "cells": [
                {"text": a.data.strftime("%d/%m/%Y") if a.data else "—"},
                {"text": a.titulo},
                {"text": str(a.peso)},
                {"text": "Notas", "url": reverse("educacao:notas_lancar", args=[a.pk])},
            ],
            "can_edit": False,
            "edit_url": "",
        })

    return render(request, "educacao/avaliacao_list.html", {
        "diario": diario,
        "can_edit": can_edit,
        "actions": actions,
        "headers": headers,
        "rows": rows,
        "page_obj": None,
    })


@login_required
@require_perm("educacao.view")
def avaliacao_create(request, pk: int):
    diario = get_object_or_404(DiarioTurma.objects.select_related("turma", "professor"), pk=pk)

    if not _can_edit_diario(request.user, diario):
        return HttpResponseForbidden("403 — Somente o professor responsável pode criar avaliação.")

    if request.method == "POST":
        form = AvaliacaoForm(request.POST)
        if form.is_valid():
            a = form.save(commit=False)
            a.diario = diario
            a.save()
            messages.success(request, "Avaliação criada com sucesso.")
            return redirect("educacao:avaliacao_list", pk=diario.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AvaliacaoForm()

    return render(request, "educacao/avaliacao_form.html", {
        "form": form,
        "diario": diario,
        "cancel_url": reverse("educacao:avaliacao_list", args=[diario.pk]),
        "submit_label": "Salvar",
        "action_url": reverse("educacao:avaliacao_create", args=[diario.pk]),
    })


@login_required
@require_perm("educacao.view")
def notas_lancar(request, pk: int):
    avaliacao = get_object_or_404(Avaliacao.objects.select_related("diario", "diario__turma", "diario__professor", "diario__turma__unidade"), pk=pk)
    diario = avaliacao.diario

    if not _can_view_diario(request.user, diario):
        return HttpResponseForbidden("403 — Você não tem permissão para acessar este diário.")

    can_edit = _can_edit_diario(request.user, diario)
    q = (request.GET.get("q") or "").strip()

    alunos_qs = (
        Matricula.objects.filter(turma=diario.turma, situacao="ATIVA")
        .select_related("aluno")
        .order_by("aluno__nome")
    )

    if q:
        alunos_qs = alunos_qs.filter(
            aluno__nome__icontains=q
        )

    notas_map = {n.aluno_id: n.valor for n in avaliacao.notas.all()}

    if request.method == "POST":
        if not can_edit:
            return HttpResponseForbidden("403 — Somente o professor responsável pode lançar notas.")

        for m in alunos_qs:
            raw = (request.POST.get(f"aluno_{m.aluno_id}") or "").strip()
            if raw == "":
                Nota.objects.filter(avaliacao=avaliacao, aluno_id=m.aluno_id).delete()
                continue
            try:
                valor = Decimal(raw.replace(",", "."))
            except (InvalidOperation, ValueError):
                messages.error(request, f"Nota inválida para {m.aluno.nome}.")
                continue

            Nota.objects.update_or_create(
                avaliacao=avaliacao,
                aluno_id=m.aluno_id,
                defaults={"valor": valor},
            )

        messages.success(request, "Notas salvas com sucesso.")
        url = reverse("educacao:notas_lancar", args=[avaliacao.pk])
        return redirect(f"{url}?q={q}" if q else url)

    export = (request.GET.get("export") or "").strip().lower()
    if export == "pdf":
        headers = ["Aluno", "Nota"]
        rows = []
        for m in alunos_qs:
            rows.append([m.aluno.nome, str(notas_map.get(m.aluno_id, "—"))])
        filtros = f"Turma={diario.turma.nome} | Avaliação={avaliacao.titulo} | Data={avaliacao.data.strftime('%d/%m/%Y') if avaliacao.data else '-'} | Busca={q or '-'}"
        return export_pdf_table(
            request,
            filename="notas.pdf",
            title="Notas — Avaliação",
            headers=headers,
            rows=rows,
            filtros=filtros,
        )

    actions = [
        {"label": "Voltar", "url": reverse("educacao:avaliacao_list", args=[diario.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Imprimir PDF", "url": (reverse("educacao:notas_lancar", args=[avaliacao.pk]) + ("?q=" + q + "&" if q else "?") + "export=pdf"), "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]
    if can_edit:
        actions.append({"label": "Salvar Notas", "url": "#notas-form", "icon": "fa-solid fa-check", "variant": "btn-primary"})

    alunos_render = []
    for m in alunos_qs:
        alunos_render.append({
            "id": m.aluno_id,
            "nome": m.aluno.nome,
            "nota": notas_map.get(m.aluno_id, ""),
        })

    return render(request, "educacao/notas_lancar.html", {
        "avaliacao": avaliacao,
        "diario": diario,
        "can_edit": can_edit,
        "actions": actions,

        "alunos_render": alunos_render,

        "q": q,
        "action_url": reverse("educacao:notas_lancar", args=[avaliacao.pk]),
        "clear_url": reverse("educacao:notas_lancar", args=[avaliacao.pk]),
        "has_filters": bool(q),
        "autocomplete_url": reverse("educacao:api_alunos_turma_suggest", args=[diario.turma.pk]),
        "autocomplete_href": reverse("educacao:notas_lancar", args=[avaliacao.pk]) + "?q={q}",
    })
