from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from apps.billing.services import MetricaLimite, verificar_limite_municipio
from apps.core.decorators import require_perm
from apps.core.rbac import can, scope_filter_alunos, scope_filter_turmas

from .forms import MatriculaForm
from .models import Aluno, Matricula, MatriculaMovimentacao, Turma
from .services_matricula import registrar_movimentacao
from .services_requisitos import (
    avaliar_requisitos_matricula,
    registrar_override_requisitos_matricula,
)


@login_required
@require_perm("educacao.view")
def matricula_create(request):
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
    if unidade_id.isdigit():
        initial["unidade"] = int(unidade_id)

    form = MatriculaForm(request.POST or None, user=request.user, initial=initial)

    turmas_qs = turmas_base_qs
    unidade_sel = (request.POST.get("unidade") or unidade_id or "").strip()
    if unidade_sel.isdigit():
        turmas_qs = turmas_qs.filter(unidade_id=int(unidade_sel))
    if "turma" in form.fields:
        form.fields["turma"].queryset = turmas_qs.order_by("-ano_letivo", "nome")

    selected_aluno = None
    selected_aluno_id = (request.POST.get("aluno") or aluno_id or "").strip()
    if selected_aluno_id.isdigit():
        selected_aluno = alunos_qs.filter(pk=int(selected_aluno_id)).first()

    if request.method == "POST":
        if form.is_valid():
            if not selected_aluno:
                messages.error(request, "Selecione um aluno antes de confirmar a matrícula.")
                return redirect("educacao:matricula_create")

            matricula = form.save(commit=False)
            matricula.aluno = selected_aluno

            if not alunos_qs.filter(pk=matricula.aluno_id).exists():
                messages.error(request, "Aluno fora do seu escopo.")
                return redirect("educacao:matricula_create")

            if not turmas_base_qs.filter(pk=matricula.turma_id).exists():
                messages.error(request, "Turma fora do seu escopo.")
                return redirect("educacao:matricula_create")

            if Matricula.objects.filter(aluno=matricula.aluno, turma=matricula.turma).exists():
                messages.warning(request, "Esse aluno já possui matrícula nessa turma.")
                return redirect(reverse("educacao:matricula_create") + f"?aluno={matricula.aluno_id}")

            avaliacao_requisitos = avaliar_requisitos_matricula(aluno=matricula.aluno, turma=matricula.turma)
            if avaliacao_requisitos.bloqueado:
                wants_override = bool(form.cleaned_data.get("override_requisitos"))
                justificativa = (form.cleaned_data.get("override_justificativa") or "").strip()
                if wants_override and justificativa:
                    registrar_override_requisitos_matricula(
                        usuario=request.user,
                        aluno=matricula.aluno,
                        turma=matricula.turma,
                        justificativa=justificativa,
                        pendencias=avaliacao_requisitos.pendencias,
                        origem="MATRICULA_RAPIDA",
                    )
                    messages.warning(request, "Matrícula liberada por override com justificativa auditada.")
                else:
                    for pendencia in avaliacao_requisitos.pendencias:
                        messages.error(request, pendencia)
                    return redirect(reverse("educacao:matricula_create") + f"?aluno={matricula.aluno_id}")
            for aviso in avaliacao_requisitos.avisos:
                messages.warning(request, aviso)

            municipio_id = (
                Turma.objects.filter(pk=matricula.turma_id)
                .values_list("unidade__secretaria__municipio_id", flat=True)
                .first()
            )
            incremento_aluno = 1
            if municipio_id:
                incremento_aluno = 0 if Matricula.objects.filter(
                    aluno_id=matricula.aluno_id,
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
                        return redirect(reverse("educacao:matricula_create") + f"?aluno={matricula.aluno_id}")

            if not matricula.data_matricula:
                matricula.data_matricula = timezone.localdate()

            matricula.save()
            registrar_movimentacao(
                matricula=matricula,
                tipo=MatriculaMovimentacao.Tipo.CRIACAO,
                usuario=request.user,
                turma_destino=matricula.turma,
                situacao_nova=matricula.situacao,
                motivo="Matrícula criada pela tela de matrícula rápida.",
            )
            messages.success(request, "Matrícula realizada com sucesso.")
            return redirect(reverse("educacao:matricula_create") + f"?aluno={matricula.aluno_id}")

        messages.error(request, "Corrija os erros do formulário.")

    actions = [
        {
            "label": "Voltar",
            "url": reverse("educacao:index"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        },
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
        top_extra = str(format_html('<input type="hidden" name="aluno" value="{}">', selected_aluno.pk))

    selected_matriculas = []
    if selected_aluno:
        selected_matriculas = list(
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
    for item in selected_matriculas:
        rows_selected_matriculas.append(
            {
                "cells": [
                    {"text": item.turma.nome, "url": reverse("educacao:turma_detail", args=[item.turma.pk])},
                    {"text": item.turma.unidade.nome},
                    {"text": str(item.turma.ano_letivo)},
                    {"text": item.get_situacao_display()},
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
