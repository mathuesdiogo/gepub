from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect
from django.urls import reverse
from urllib.parse import urlencode

from apps.billing.services import MetricaLimite, verificar_limite_municipio
from apps.core.decorators import require_perm
from apps.core.rbac import can, scope_filter_alunos, scope_filter_turmas

from .models import Aluno, Turma, Matricula
from .forms import MatriculaForm
from .services_matricula import registrar_movimentacao


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

    if q and not aluno_id:
        alunos_filtrados = alunos_qs.filter(
            Q(nome__icontains=q)
            | Q(cpf__icontains=q)
            | Q(nis__icontains=q)
            | Q(nome_mae__icontains=q)
        ).order_by("nome")
        if alunos_filtrados.count() == 1:
            unico = alunos_filtrados.first()
            return redirect(f"{reverse('educacao:matricula_create')}?aluno={unico.pk}&q={q}")

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

    selected_aluno = None
    if aluno_id.isdigit():
        selected_aluno = alunos_qs.filter(pk=int(aluno_id)).first()

    if request.method == "POST":
        post_aluno_id = (request.POST.get("aluno") or aluno_id or "").strip()
        if post_aluno_id.isdigit():
            selected_aluno = alunos_qs.filter(pk=int(post_aluno_id)).first()
        if form.is_valid():
            m = form.save(commit=False)
            if not selected_aluno:
                messages.error(request, "Selecione um aluno antes de confirmar a matrícula.")
                return redirect("educacao:matricula_create")
            m.aluno = selected_aluno

            if not alunos_qs.filter(pk=m.aluno_id).exists():
                messages.error(request, "Aluno fora do seu escopo.")
                return redirect("educacao:matricula_create")

            if not turmas_base_qs.filter(pk=m.turma_id).exists():
                messages.error(request, "Turma fora do seu escopo.")
                return redirect("educacao:matricula_create")

            if Matricula.objects.filter(aluno=m.aluno, turma=m.turma).exists():
                messages.warning(request, "Esse aluno já possui matrícula nessa turma.")
            else:
                municipio_id = (
                    Turma.objects.filter(pk=m.turma_id)
                    .values_list("unidade__secretaria__municipio_id", flat=True)
                    .first()
                )
                incremento_aluno = 1
                if municipio_id:
                    incremento_aluno = 0 if Matricula.objects.filter(
                        aluno_id=m.aluno_id,
                        turma__unidade__secretaria__municipio_id=municipio_id,
                        situacao=Matricula.Situacao.ATIVA,
                    ).exists() else 1

                if municipio_id and incremento_aluno > 0:
                    from apps.org.models import Municipio

                    municipio = Municipio.objects.filter(pk=municipio_id).first()
                    if municipio:
                        limite = verificar_limite_municipio(
                            municipio,
                            MetricaLimite.ALUNOS,
                            incremento=incremento_aluno,
                        )
                        if not limite.permitido:
                            upgrade_url = reverse("billing:solicitar_upgrade")
                            upgrade_url += f"?municipio={municipio.pk}&tipo=ALUNOS&qtd={limite.excedente}"
                            messages.error(
                                request,
                                (
                                    f"Limite de alunos excedido ({limite.atual}/{limite.limite}). "
                                    f"Solicite upgrade em: {upgrade_url}"
                                ),
                            )
                            return redirect(reverse("educacao:matricula_create") + f"?aluno={m.aluno_id}")

                m.save()
                registrar_movimentacao(
                    matricula=m,
                    tipo="CRIACAO",
                    usuario=request.user,
                    turma_destino=m.turma,
                    situacao_nova=m.situacao,
                    motivo="Matrícula criada pela tela de matrícula rápida.",
                )
                messages.success(request, "Matrícula realizada com sucesso.")
                return redirect(reverse("educacao:matricula_create") + f"?aluno={m.aluno_id}")

        messages.error(request, "Corrija os erros do formulário.")

    actions = [
        {"label": "Voltar", "url": reverse("educacao:index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
    ]

    query = {}
    if q:
        query["q"] = q
    if aluno_id:
        query["aluno"] = aluno_id
    if unidade_id:
        query["unidade"] = unidade_id
    form_action_url = reverse("educacao:matricula_create")
    if query:
        form_action_url = f"{form_action_url}?{urlencode(query)}"

    top_extra = ""
    if selected_aluno:
        top_extra = f'<input type="hidden" name="aluno" value="{selected_aluno.pk}">'

    selected_matriculas = []
    if selected_aluno:
        selected_matriculas = (
            Matricula.objects.select_related("turma", "turma__unidade")
            .filter(aluno=selected_aluno, turma__in=turmas_base_qs)
            .order_by("-id")[:8]
        )

    headers_selected_matriculas = [
        {"label": "Turma"},
        {"label": "Unidade"},
        {"label": "Ano", "width": "90px"},
        {"label": "Situação", "width": "130px"},
    ]
    rows_selected_matriculas = []
    for m in selected_matriculas:
        rows_selected_matriculas.append(
            {
                "cells": [
                    {"text": m.turma.nome, "url": reverse("educacao:turma_detail", args=[m.turma.pk])},
                    {"text": m.turma.unidade.nome},
                    {"text": str(m.turma.ano_letivo)},
                    {"text": m.get_situacao_display()},
                ]
            }
        )

    return render(
        request,
        "educacao/matricula_create.html",
        {
            "q": q,
            "unidade": unidade_id,
            "actions": actions,
            "search_action_url": reverse("educacao:matricula_create"),
            "form_action_url": form_action_url,
            "clear_url": reverse("educacao:matricula_create"),
            "has_filters": bool(q),
            "form": form,
            "top_extra": top_extra,
            "selected_aluno": selected_aluno,
            "autocomplete_url": reverse("educacao:api_alunos_suggest"),
            "headers_selected_matriculas": headers_selected_matriculas,
            "rows_selected_matriculas": rows_selected_matriculas,
        },
    )
