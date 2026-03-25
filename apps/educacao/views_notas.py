from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.exports import export_pdf_table
from apps.core.rbac import can, is_professor_profile_role, scope_filter_turmas

from .forms_notas import AvaliacaoForm
from .models import Matricula, Turma
from .models_diario import (
    AVALIACAO_CONCEITOS_CHOICES,
    Avaliacao,
    DiarioTurma,
    Nota,
)


def _is_professor(user) -> bool:
    return is_professor_profile_role(getattr(getattr(user, "profile", None), "role", None))


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


def _lancada_expr():
    return Q(valor__isnull=False) | ~Q(conceito="")


def _parse_decimal(value: str) -> Decimal | None:
    raw = (value or "").strip().replace(",", ".")
    if not raw:
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


def _normalize_conceito(value: str) -> str:
    conceito = (value or "").strip().upper()
    validos = {item[0] for item in AVALIACAO_CONCEITOS_CHOICES}
    return conceito if conceito in validos else ""


def _instrumento_badge(avaliacao: Avaliacao) -> str:
    sigla = (avaliacao.sigla or "").strip().upper()
    tipo = avaliacao.get_tipo_display()
    return f"{sigla} • {tipo}" if sigla else tipo


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

    q = (request.GET.get("q") or "").strip()
    qs = Avaliacao.objects.filter(diario=diario)
    if q:
        qs = qs.filter(
            Q(titulo__icontains=q)
            | Q(sigla__icontains=q)
            | Q(tipo__icontains=q)
            | Q(descricao__icontains=q)
            | Q(periodo__nome__icontains=q)
        )
    qs = qs.order_by("-data", "-id")

    export = (request.GET.get("export") or "").strip().lower()
    if export == "pdf":
        headers = ["Data", "Instrumento", "Título", "Etapa", "Modo", "Lançadas", "Peso"]
        rows = []
        lancadas_map = {
            row["avaliacao_id"]: row["total"]
            for row in Nota.objects.filter(avaliacao_id__in=[a.id for a in qs]).filter(_lancada_expr()).values("avaliacao_id").annotate(total=Count("id"))
        }
        for a in qs:
            rows.append([
                a.data.strftime("%d/%m/%Y") if a.data else "—",
                _instrumento_badge(a),
                a.titulo or "—",
                str(a.periodo) if a.periodo else "—",
                a.get_modo_registro_display(),
                str(lancadas_map.get(a.id, 0)),
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
        {"label": "Voltar", "url": reverse("educacao:diario_detail", args=[diario.pk]), "icon": "fa-solid fa-arrow-left", "variant": "gp-button--ghost"},
        {"label": "Imprimir PDF", "url": reverse("educacao:avaliacao_list", args=[diario.pk]) + "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "gp-button--ghost"},
    ]
    if can_edit:
        actions.append({"label": "Nova Avaliação", "url": reverse("educacao:avaliacao_create", args=[diario.pk]), "icon": "fa-solid fa-plus", "variant": "gp-button--primary"})

    stats_map = {
        row["avaliacao_id"]: row["lancadas"]
        for row in Nota.objects.filter(avaliacao_id__in=[a.id for a in qs]).values("avaliacao_id").annotate(lancadas=Count("id", filter=_lancada_expr()))
    }
    headers = [
        {"label": "Data", "width": "110px"},
        {"label": "Instrumento", "width": "180px"},
        {"label": "Avaliação"},
        {"label": "Etapa", "width": "140px"},
        {"label": "Modo", "width": "110px"},
        {"label": "Lançadas", "width": "95px"},
        {"label": "Ações", "width": "280px"},
    ]
    rows = []
    for a in qs:
        editar_link = ""
        if can_edit:
            editar_link = (
                f'<a class="gp-button gp-button--outline" href="{reverse("educacao:avaliacao_update", args=[diario.pk, a.pk])}">'
                '<i class="fa-solid fa-sliders"></i>Configurar</a>'
            )
        acoes = [
            f'<a class="gp-button gp-button--outline" href="{reverse("educacao:notas_lancar", args=[a.pk])}">'
            '<i class="fa-solid fa-clipboard-check"></i>Registrar</a>'
        ]
        if editar_link:
            acoes.append(editar_link)
        rows.append({
            "cells": [
                {"text": a.data.strftime("%d/%m/%Y") if a.data else "—"},
                {"text": _instrumento_badge(a)},
                {"text": a.titulo or "—"},
                {"text": str(a.periodo) if a.periodo else "—"},
                {"text": a.get_modo_registro_display()},
                {"text": str(stats_map.get(a.id, 0))},
                {"html": '<div class="gp-professor-inline-actions">' + "".join(acoes) + "</div>"},
            ],
            "can_edit": False,
            "edit_url": "",
        })

    return render(request, "educacao/avaliacao_list.html", {
        "diario": diario,
        "can_edit": can_edit,
        "actions": actions,
        "q": q,
        "action_url": reverse("educacao:avaliacao_list", args=[diario.pk]),
        "clear_url": reverse("educacao:avaliacao_list", args=[diario.pk]),
        "has_filters": bool(q),
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
        form = AvaliacaoForm(request.POST, diario=diario)
        if form.is_valid():
            avaliacao = form.save(commit=False)
            avaliacao.diario = diario
            avaliacao.save()
            messages.success(request, "Avaliação criada com sucesso.")
            return redirect("educacao:avaliacao_list", pk=diario.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AvaliacaoForm(
            diario=diario,
            initial={
                "tipo": "PROVA",
                "modo_registro": "NOTA",
                "peso": Decimal("1.00"),
                "nota_maxima": Decimal("10.00"),
            },
        )

    return render(request, "educacao/avaliacao_form.html", {
        "diario": diario,
        "form": form,
        "mode": "create",
        "cancel_url": reverse("educacao:avaliacao_list", args=[diario.pk]),
        "action_url": reverse("educacao:avaliacao_create", args=[diario.pk]),
        "submit_label": "Salvar instrumento",
    })


@login_required
@require_perm("educacao.view")
def avaliacao_update(request, pk: int, avaliacao_id: int):
    diario = get_object_or_404(
        DiarioTurma.objects.select_related("turma", "turma__unidade", "professor"),
        pk=pk,
    )

    if not _can_view_diario(request.user, diario):
        return HttpResponseForbidden("403 — Você não tem permissão para acessar este diário.")

    if not _can_edit_diario(request.user, diario):
        return HttpResponseForbidden("403 — Somente o professor responsável pode editar a configuração.")

    avaliacao = get_object_or_404(Avaliacao, pk=avaliacao_id, diario=diario)
    if request.method == "POST":
        form = AvaliacaoForm(request.POST, instance=avaliacao, diario=diario)
        if form.is_valid():
            form.save()
            messages.success(request, "Configuração da avaliação atualizada com sucesso.")
            return redirect("educacao:avaliacao_list", pk=diario.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AvaliacaoForm(instance=avaliacao, diario=diario)

    return render(request, "educacao/avaliacao_form.html", {
        "diario": diario,
        "form": form,
        "avaliacao": avaliacao,
        "mode": "update",
        "cancel_url": reverse("educacao:avaliacao_list", args=[diario.pk]),
        "action_url": reverse("educacao:avaliacao_update", args=[diario.pk, avaliacao.pk]),
        "submit_label": "Editar configuração",
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
    is_modo_conceito = avaliacao.modo_registro == "CONCEITO"

    # ===== POST (salvar notas) =====
    if request.method == "POST":
        if not can_edit:
            return HttpResponseForbidden("403 — Somente o professor responsável pode lançar notas.")

        with transaction.atomic():
            for m in alunos_qs:
                raw = request.POST.get(f"mat_{m.id}") or ""
                if is_modo_conceito:
                    conceito = _normalize_conceito(raw)
                    defaults = {"valor": None, "conceito": conceito}
                else:
                    valor = _parse_decimal(raw)
                    defaults = {"valor": valor, "conceito": ""}

                Nota.objects.update_or_create(
                    avaliacao=avaliacao,
                    aluno=m.aluno,
                    defaults=defaults,
                )

        messages.success(
            request,
            "Conceitos salvos com sucesso." if is_modo_conceito else "Notas salvas com sucesso.",
        )
        return redirect("educacao:notas_lancar", pk=avaliacao.pk)

    # ===== PDF =====
    export = (request.GET.get("export") or "").strip().lower()
    if export == "pdf":
        headers = ["Aluno", "Conceito" if is_modo_conceito else "Nota"]
        rows = []
        for m in alunos_qs:
            nota_obj = notas_existentes.get(m.aluno_id)
            rows.append([
                m.aluno.nome,
                (
                    (nota_obj.conceito or "—")
                    if is_modo_conceito
                    else (str(nota_obj.valor).replace(".", ",") if nota_obj and nota_obj.valor is not None else "—")
                ),
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
            "variant": "gp-button--ghost",
        },
        {
            "label": "Imprimir PDF",
            "url": reverse("educacao:notas_lancar", args=[avaliacao.pk]) + "?export=pdf",
            "icon": "fa-solid fa-file-pdf",
            "variant": "gp-button--ghost",
        },
    ]
    if can_edit:
        actions.append(
            {
                "label": "Salvar conceitos" if is_modo_conceito else "Salvar notas",
                "url": "#notas-form",
                "icon": "fa-solid fa-check",
                "variant": "gp-button--primary",
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
                "conceito": "" if not nota_obj else (nota_obj.conceito or ""),
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
            "is_modo_conceito": is_modo_conceito,
            "conceito_choices": AVALIACAO_CONCEITOS_CHOICES,
        },
    )
