from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.exports import export_pdf_table
from apps.core.rbac import can, scope_filter_turmas

from .forms_notas import AvaliacaoForm
from .models import Matricula, Turma
from .models_diario import DiarioTurma, Avaliacao, Nota


def _is_professor(user) -> bool:
    return getattr(getattr(user, "profile", None), "role", "") == "PROFESSOR"


def _can_edit_diario(user, diario: DiarioTurma) -> bool:
    # Professor responsável edita; gestores/admin podem visualizar/imprimir.
    if can(user, "educacao.manage"):
        return True
    if not _is_professor(user):
        return False
    return getattr(diario, "professor_id", None) == getattr(user, "id", None)


def _can_view_diario(user, diario: DiarioTurma) -> bool:
    # Quem tem permissão de view e está no escopo da turma pode ver.
    if not can(user, "educacao.view"):
        return False
    turma_ok = scope_filter_turmas(user, Turma.objects.filter(pk=diario.turma_id)).exists()
    return turma_ok


@login_required
@require_perm("educacao.view")
def avaliacao_list(request, pk: int):
    diario = get_object_or_404(
        DiarioTurma.objects.select_related("turma", "turma__unidade", "professor"),
        pk=pk,
    )

    if not _can_view_diario(request.user, diario):
        return HttpResponseForbidden("403 — Você não tem permissão para acessar este diário.")

    can_edit = _can_edit_diario(request.user, diario)

    qs = Avaliacao.objects.filter(diario=diario).order_by("-data", "-id")

    export = (request.GET.get("export") or "").strip().lower()
    if export == "pdf":
        headers = ["Título", "Data", "Peso"]
        rows = []
        for a in qs:
            rows.append([
                a.titulo or "—",
                a.data.strftime("%d/%m/%Y") if a.data else "—",
                str(a.peso) if a.peso is not None else "—",
            ])

        filtros = f"Turma={diario.turma.nome} | Ano={diario.ano_letivo} | Professor={getattr(diario.professor, 'username', '-')}"
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

    headers = [{"label": "Título"}, {"label": "Data", "width": "140px"}, {"label": "Peso", "width": "110px"}, {"label": "Ações", "width": "180px"}]
    rows = []
    for a in qs:
        rows.append({
            "cells": [
                {"text": a.titulo or "—"},
                {"text": a.data.strftime("%d/%m/%Y") if a.data else "—"},
                {"text": str(a.peso) if a.peso is not None else "—"},
                {"text": "Lançar notas", "url": reverse("educacao:notas_lancar", args=[a.pk])},
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
    diario = get_object_or_404(
        DiarioTurma.objects.select_related("turma", "turma__unidade", "professor"),
        pk=pk,
    )

    if not _can_view_diario(request.user, diario):
        return HttpResponseForbidden("403 — Você não tem permissão para acessar este diário.")

    if not _can_edit_diario(request.user, diario):
        return HttpResponseForbidden("403 — Somente o professor responsável pode criar avaliações.")

    if request.method == "POST":
        form = AvaliacaoForm(request.POST)
        if form.is_valid():
            avaliacao = form.save(commit=False)
            avaliacao.diario = diario
            avaliacao.save()
            messages.success(request, "Avaliação criada com sucesso.")
            return redirect("educacao:avaliacao_list", pk=diario.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AvaliacaoForm()

    return render(request, "educacao/avaliacao_form.html", {
        "diario": diario,
        "form": form,
        "mode": "create",
        "cancel_url": reverse("educacao:avaliacao_list", args=[diario.pk]),
        "action_url": reverse("educacao:avaliacao_create", args=[diario.pk]),
        "submit_label": "Salvar",
    })


@login_required
@require_perm("educacao.view")
def notas_lancar(request, pk: int):
    """
    pk = Avaliacao.id
    """
    avaliacao = get_object_or_404(
        Avaliacao.objects.select_related("diario", "periodo"),
        pk=pk,
    )
    diario = avaliacao.diario

    # permissão: visualizar (gestor/unidade pode ver/imprimir)
    if not _can_view_diario(request.user, diario):
        return HttpResponseForbidden("403 — Você não tem permissão para acessar este diário/avaliação.")

    # permissão: editar (apenas professor responsável)
    can_edit = _can_edit_diario(request.user, diario)

    # alunos ativos da turma do diário
    alunos_qs = (
        Matricula.objects.filter(turma=diario.turma, situacao=Matricula.Situacao.ATIVA)
        .select_related("aluno")
        .order_by("aluno__nome")
    )

    # mapa de notas existentes
    notas_existentes = {
        n.aluno_id: n for n in Nota.objects.filter(avaliacao=avaliacao).select_related("aluno")
    }

    # ===== POST (salvar notas) =====
    if request.method == "POST":
        if not can_edit:
            return HttpResponseForbidden("403 — Somente o professor responsável pode lançar notas.")

        with transaction.atomic():
            for m in alunos_qs:
                raw = (request.POST.get(f"mat_{m.id}") or "").strip()
                if raw == "":
                    valor = None
                else:
                    try:
                        valor = float(raw.replace(",", "."))
                    except ValueError:
                        valor = None

                Nota.objects.update_or_create(
                    avaliacao=avaliacao,
                    aluno=m.aluno,
                    defaults={"valor": valor},
                )

        messages.success(request, "Notas salvas com sucesso.")
        return redirect("educacao:notas_lancar", pk=avaliacao.pk)

    # ===== PDF =====
    export = (request.GET.get("export") or "").strip().lower()
    if export == "pdf":
        headers = ["Aluno", "Nota"]
        rows = []
        for m in alunos_qs:
            nota_obj = notas_existentes.get(m.aluno_id)
            rows.append([
                m.aluno.nome,
                (str(nota_obj.valor).replace(".", ",") if nota_obj and nota_obj.valor is not None else "—"),
            ])

        filtros = f"Turma={diario.turma.nome} | Avaliação={avaliacao.titulo} | Período={str(avaliacao.periodo) if avaliacao.periodo else '-'}"
        return export_pdf_table(
            request,
            filename="lancamento_notas.pdf",
            title="Lançamento de Notas",
            headers=headers,
            rows=rows,
            filtros=filtros,
        )

    # ===== ações =====
    actions = [
        {
            "label": "Voltar",
            "url": reverse("educacao:avaliacao_list", args=[diario.pk]),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        },
        {
            "label": "Imprimir PDF",
            "url": reverse("educacao:notas_lancar", args=[avaliacao.pk]) + "?export=pdf",
            "icon": "fa-solid fa-file-pdf",
            "variant": "btn--ghost",
        },
    ]
    if can_edit:
        actions.append(
            {
                "label": "Salvar",
                "url": "#notas-form",
                "icon": "fa-solid fa-check",
                "variant": "btn-primary",
            }
        )

    # ✅ lista pronta pro template (compatível com templates do GEPUB)
    alunos_render = []
    for m in alunos_qs:
        nota_obj = notas_existentes.get(m.aluno_id)
        alunos_render.append(
            {
                "matricula_id": m.id,
                "aluno_id": m.aluno_id,
                "aluno_nome": m.aluno.nome,
                "valor": "" if (not nota_obj or nota_obj.valor is None) else str(nota_obj.valor).replace(".", ","),
            }
        )

    return render(
        request,
        "educacao/notas_lancar.html",
        {
            "avaliacao": avaliacao,
            "diario": diario,
            "turma": diario.turma,
            "can_edit": can_edit,
            "actions": actions,
            "alunos_render": alunos_render,
        },
    )
