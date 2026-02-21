from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.html import escape

from apps.core.decorators import require_perm
from apps.core.rbac import can, scope_filter_alunos, scope_filter_turmas

from .models import Aluno, Turma, Matricula
from .forms import MatriculaForm


@login_required
@require_perm("educacao.view")
def matricula_create(request):
    # Mantém a regra que você já usa: precisa de manage para efetivar matrícula
    if not can(request.user, "educacao.manage"):
        messages.error(request, "Você não tem permissão para realizar matrículas.")
        return redirect("educacao:index")

    q = (request.GET.get("q") or "").strip()
    aluno_id = (request.GET.get("aluno") or "").strip()
    unidade_id = (request.GET.get("unidade") or "").strip()

    alunos_qs = scope_filter_alunos(
        request.user,
        Aluno.objects.only("id", "nome", "cpf", "nis", "nome_mae", "ativo"),
    )

    turmas_base_qs = scope_filter_turmas(
        request.user,
        Turma.objects.select_related(
            "unidade",
            "unidade__secretaria",
            "unidade__secretaria__municipio",
        ),
    )

    alunos_result = alunos_qs
    if q:
        alunos_result = alunos_result.filter(
            Q(nome__icontains=q)
            | Q(cpf__icontains=q)
            | Q(nis__icontains=q)
            | Q(nome_mae__icontains=q)
        )
    alunos_result = alunos_result.order_by("nome")[:25]

    initial = {}
    if aluno_id.isdigit():
        initial["aluno"] = int(aluno_id)
    if unidade_id.isdigit():
        initial["unidade"] = int(unidade_id)

    form = MatriculaForm(request.POST or None, initial=initial)

    # Mantém querysets restritos ao escopo
    if "aluno" in form.fields:
        form.fields["aluno"].queryset = alunos_qs.order_by("nome")

    if "unidade" in form.fields:
        unidades_ids = turmas_base_qs.values_list("unidade_id", flat=True).distinct()
        form.fields["unidade"].queryset = form.fields["unidade"].queryset.filter(id__in=unidades_ids)

    turmas_qs = turmas_base_qs
    unidade_sel = (request.POST.get("unidade") or unidade_id or "").strip()
    if unidade_sel.isdigit():
        turmas_qs = turmas_qs.filter(unidade_id=int(unidade_sel))

    if "turma" in form.fields:
        form.fields["turma"].queryset = turmas_qs.order_by("-ano_letivo", "nome")

    if request.method == "POST":
        if form.is_valid():
            m = form.save(commit=False)

            if not alunos_qs.filter(pk=m.aluno_id).exists():
                messages.error(request, "Aluno fora do seu escopo.")
                return redirect("educacao:matricula_create")

            if not turmas_base_qs.filter(pk=m.turma_id).exists():
                messages.error(request, "Turma fora do seu escopo.")
                return redirect("educacao:matricula_create")

            if Matricula.objects.filter(aluno=m.aluno, turma=m.turma).exists():
                messages.warning(request, "Esse aluno já possui matrícula nessa turma.")
            else:
                m.save()
                messages.success(request, "Matrícula realizada com sucesso.")
                return redirect(reverse("educacao:matricula_create") + f"?aluno={m.aluno_id}")

        messages.error(request, "Corrija os erros do formulário.")

    headers = [
        {"label": "Aluno"},
        {"label": "CPF", "width": "160px"},
        {"label": "NIS", "width": "160px"},
    ]

    rows = []
    for a in alunos_result:
        url = reverse("educacao:matricula_create") + f"?q={escape(q)}&aluno={a.pk}"
        if unidade_id:
            url += f"&unidade={escape(unidade_id)}"

        rows.append(
            {
                "cells": [
                    {"text": a.nome, "url": reverse("educacao:aluno_detail", args=[a.pk])},
                    {"text": a.cpf or "—", "url": ""},
                    {"text": a.nis or "—", "url": ""},
                ],
                "can_edit": True,
                "edit_url": url,
            }
        )

    actions = [
        {"label": "Voltar", "url": reverse("educacao:index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
    ]

    return render(
        request,
        "educacao/matricula_create.html",
        {
            "q": q,
            "unidade": unidade_id,
            "alunos_result": alunos_result,
            "page_obj": None,
            "headers": headers,
            "rows": rows,
            "actions": actions,
            "action_url": reverse("educacao:matricula_create"),
            "clear_url": reverse("educacao:matricula_create"),
            "has_filters": bool(q),
            "form": form,
            "actions_partial": "educacao/partials/matricula_pick_action.html",
        },
    )