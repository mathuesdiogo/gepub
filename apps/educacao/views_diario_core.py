from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.exports import export_pdf_table
from apps.core.rbac import can, scope_filter_turmas

from .forms_diario import AulaForm
from .models import Turma, Matricula
from .models_diario import DiarioTurma, Aula
from .services_requisitos import registrar_override_requisitos_lancamento
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
        headers = ["Data", "Qtd", "Tipo", "Etapa", "Componente", "Conteúdo", "URL", "Observações"]
        rows = []
        for a in aulas:
            rows.append([
                a.data.strftime("%d/%m/%Y") if a.data else "—",
                str(a.quantidade_aulas or 1),
                a.get_tipo_aula_display(),
                str(a.periodo) if a.periodo else "—",
                str(a.componente) if a.componente else "—",
                (a.conteudo or "—")[:80],
                (a.url_atividade or "—")[:80],
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
            "variant": "gp-button--ghost",
        },
        {
            "label": "Imprimir PDF",
            "url": reverse("educacao:diario_detail", args=[diario.pk]) + "?export=pdf",
            "icon": "fa-solid fa-file-pdf",
            "variant": "gp-button--ghost",
        },
        {
            "label": "Avaliações",
            "url": reverse("educacao:avaliacao_list", args=[diario.pk]),
            "icon": "fa-solid fa-clipboard-check",
            "variant": "gp-button--ghost",
        },
    ]

    if can_edit or can(request.user, "educacao.manage"):
        actions.append(
            {
                "label": "Justificativas de Falta",
                "url": reverse("educacao:justificativa_falta_list"),
                "icon": "fa-solid fa-file-signature",
                "variant": "gp-button--ghost",
            }
        )

    if can_edit:
        actions.append(
            {
                "label": "Nova Aula",
                "url": reverse("educacao:aula_create", args=[diario.pk]),
                "icon": "fa-solid fa-plus",
                "variant": "gp-button--primary",
            }
        )

    headers = [
        {"label": "Data", "width": "140px"},
        {"label": "Qtd", "width": "70px"},
        {"label": "Tipo", "width": "130px"},
        {"label": "Etapa", "width": "170px"},
        {"label": "Componente", "width": "170px"},
        {"label": "Conteúdo"},
        {"label": "URL", "width": "150px"},
        {"label": "Ações", "width": "250px"},
    ]

    rows = []
    for a in aulas:
        acoes = [
            {
                "label": "Frequência",
                "url": reverse("educacao:aula_frequencia", args=[diario.pk, a.pk]),
            }
        ]
        if can_edit:
            acoes.append(
                {
                    "label": "Editar aula",
                    "url": reverse("educacao:aula_update", args=[diario.pk, a.pk]),
                }
            )
        acoes_html = '<div class="gp-professor-inline-actions">' + "".join(
            f'<a class="gp-button gp-button--outline" href="{item["url"]}">{item["label"]}</a>'
            for item in acoes
        ) + "</div>"
        rows.append(
            {
                "cells": [
                    {"text": a.data.strftime("%d/%m/%Y") if a.data else "—", "url": ""},
                    {"text": str(a.quantidade_aulas or 1)},
                    {"text": a.get_tipo_aula_display()},
                    {"text": str(a.periodo) if a.periodo else "—"},
                    {"text": str(a.componente) if a.componente else "—"},
                    {"text": (a.conteudo or "—")[:120]},
                    {"text": "Visualizar link", "url": a.url_atividade} if a.url_atividade else {"text": "—"},
                    {"html": acoes_html},
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
        form = AulaForm(request.POST, diario=diario, user=request.user)
        if form.is_valid():
            aula = form.save(commit=False)
            aula.diario = diario
            aula.save()
            form.save_m2m()
            override_payload = getattr(form, "override_requisitos_payload", {}) or {}
            if override_payload:
                registrar_override_requisitos_lancamento(
                    usuario=request.user,
                    turma=diario.turma,
                    componente_id=getattr(aula, "componente_id", None) or 0,
                    aula_id=aula.id,
                    justificativa=override_payload.get("justificativa", ""),
                    pendencias=override_payload.get("pendencias", []),
                    origem="AULA_CREATE",
                )
                messages.warning(request, "Lançamento liberado por override com justificativa auditada.")
            for aviso in getattr(form, "requisito_avisos", []) or []:
                messages.warning(request, aviso)
            messages.success(request, "Aula criada com sucesso.")
            return redirect("educacao:diario_detail", pk=diario.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AulaForm(diario=diario, user=request.user)

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
        form = AulaForm(request.POST, instance=aula, diario=diario, user=request.user)
        if form.is_valid():
            form.save()
            override_payload = getattr(form, "override_requisitos_payload", {}) or {}
            if override_payload:
                registrar_override_requisitos_lancamento(
                    usuario=request.user,
                    turma=diario.turma,
                    componente_id=getattr(aula, "componente_id", None) or 0,
                    aula_id=aula.id,
                    justificativa=override_payload.get("justificativa", ""),
                    pendencias=override_payload.get("pendencias", []),
                    origem="AULA_UPDATE",
                )
                messages.warning(request, "Atualização liberada por override com justificativa auditada.")
            for aviso in getattr(form, "requisito_avisos", []) or []:
                messages.warning(request, aviso)
            messages.success(request, "Aula atualizada com sucesso.")
            return redirect("educacao:diario_detail", pk=diario.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AulaForm(instance=aula, diario=diario, user=request.user)

    return render(
        request,
        "educacao/aula_form.html",
        {
            "form": form,
            "diario": diario,
            "aula": aula,
            "mode": "update",
            "cancel_url": reverse("educacao:diario_detail", args=[diario.pk]),
            "submit_label": "Editar",
            "action_url": reverse("educacao:aula_update", args=[diario.pk, aula.pk]),
            "bncc_hint": getattr(form, "bncc_hint", ""),
        },
    )


def diario_create_for_turma_impl(request, pk: int):
    turma_qs = scope_filter_turmas(request.user, Turma.objects.select_related("unidade"))
    turma = get_object_or_404(turma_qs, pk=pk)

    if not is_professor(request.user):
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
            "variant": "gp-button--ghost",
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
