from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import can, scope_filter_unidades
from apps.org.models import Unidade

from .forms import AgendamentoSaudeForm
from .models import AgendamentoSaude, ProfissionalSaude


def _scoped_unidades(user):
    return scope_filter_unidades(user, Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE).order_by("nome"))


def _scoped_profissionais(unidades_qs):
    return ProfissionalSaude.objects.filter(unidade_id__in=unidades_qs.values_list("id", flat=True), ativo=True).order_by("nome")


@login_required
@require_perm("saude.view")
def agenda_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()

    unidades_qs = _scoped_unidades(request.user)
    qs = AgendamentoSaude.objects.select_related("unidade", "profissional", "especialidade", "sala").filter(
        unidade_id__in=unidades_qs.values_list("id", flat=True)
    )

    if q:
        qs = qs.filter(
            Q(paciente_nome__icontains=q)
            | Q(paciente_cpf__icontains=q)
            | Q(profissional__nome__icontains=q)
            | Q(unidade__nome__icontains=q)
        )

    if status:
        qs = qs.filter(status=status)

    qs = qs.order_by("-inicio", "-id")

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    can_manage = can(request.user, "saude.manage")

    actions = []
    if can_manage:
        actions.append({"label": "Novo Agendamento", "url": reverse("saude:agenda_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})

    headers = [
        {"label": "Paciente"},
        {"label": "Início", "width": "170px"},
        {"label": "Profissional"},
        {"label": "Unidade"},
        {"label": "Status", "width": "150px"},
    ]

    rows = []
    for a in page_obj:
        rows.append(
            {
                "cells": [
                    {"text": a.paciente_nome, "url": reverse("saude:agenda_detail", args=[a.pk])},
                    {"text": a.inicio.strftime("%d/%m/%Y %H:%M")},
                    {"text": getattr(a.profissional, "nome", "—")},
                    {"text": getattr(a.unidade, "nome", "—")},
                    {"text": a.get_status_display()},
                ],
                "can_edit": bool(can_manage),
                "edit_url": reverse("saude:agenda_update", args=[a.pk]) if can_manage else "",
            }
        )

    extra_filters = """
      <div class=\"filter-bar__field\">
        <label class=\"small\">Status</label>
        <select name=\"status\">
          <option value=\"\">Todos</option>
    """
    for k, v in AgendamentoSaude.Status.choices:
        selected = "selected" if status == k else ""
        extra_filters += f"<option value=\"{k}\" {selected}>{v}</option>"
    extra_filters += """
        </select>
      </div>
    """

    return render(
        request,
        "saude/agenda_list.html",
        {
            "q": q,
            "status": status,
            "page_obj": page_obj,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "action_url": reverse("saude:agenda_list"),
            "clear_url": reverse("saude:agenda_list"),
            "has_filters": bool(status),
            "extra_filters": extra_filters,
        },
    )


@login_required
@require_perm("saude.manage")
def agenda_create(request):
    unidades_qs = _scoped_unidades(request.user)
    profissionais_qs = _scoped_profissionais(unidades_qs)

    if request.method == "POST":
        form = AgendamentoSaudeForm(request.POST, unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)
        if form.is_valid():
            obj = form.save(commit=False)

            if not unidades_qs.filter(pk=obj.unidade_id).exists():
                messages.error(request, "Unidade fora do seu escopo.")
                return redirect("saude:agenda_create")

            if not profissionais_qs.filter(pk=obj.profissional_id).exists():
                messages.error(request, "Profissional fora do seu escopo.")
                return redirect("saude:agenda_create")

            if obj.profissional.unidade_id != obj.unidade_id:
                messages.error(request, "O profissional selecionado não pertence à unidade escolhida.")
                return redirect("saude:agenda_create")

            obj.save()
            messages.success(request, "Agendamento criado com sucesso.")
            return redirect("saude:agenda_detail", obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AgendamentoSaudeForm(unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)

    return render(
        request,
        "saude/agenda_form.html",
        {
            "form": form,
            "mode": "create",
            "cancel_url": reverse("saude:agenda_list"),
            "submit_label": "Salvar",
            "action_url": reverse("saude:agenda_create"),
        },
    )


@login_required
@require_perm("saude.manage")
def agenda_update(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    profissionais_qs = _scoped_profissionais(unidades_qs)

    qs = AgendamentoSaude.objects.select_related("unidade", "profissional").filter(
        unidade_id__in=unidades_qs.values_list("id", flat=True)
    )
    obj = get_object_or_404(qs, pk=pk)

    if request.method == "POST":
        form = AgendamentoSaudeForm(request.POST, instance=obj, unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)
        if form.is_valid():
            obj2 = form.save(commit=False)

            if not unidades_qs.filter(pk=obj2.unidade_id).exists():
                messages.error(request, "Unidade fora do seu escopo.")
                return redirect("saude:agenda_update", pk=obj.pk)

            if not profissionais_qs.filter(pk=obj2.profissional_id).exists():
                messages.error(request, "Profissional fora do seu escopo.")
                return redirect("saude:agenda_update", pk=obj.pk)

            if obj2.profissional.unidade_id != obj2.unidade_id:
                messages.error(request, "O profissional selecionado não pertence à unidade escolhida.")
                return redirect("saude:agenda_update", pk=obj.pk)

            obj2.save()
            messages.success(request, "Agendamento atualizado com sucesso.")
            return redirect("saude:agenda_detail", obj2.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AgendamentoSaudeForm(instance=obj, unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)

    return render(
        request,
        "saude/agenda_form.html",
        {
            "form": form,
            "mode": "update",
            "obj": obj,
            "cancel_url": reverse("saude:agenda_detail", args=[obj.pk]),
            "submit_label": "Salvar",
            "action_url": reverse("saude:agenda_update", args=[obj.pk]),
        },
    )


@login_required
@require_perm("saude.view")
def agenda_detail(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    qs = AgendamentoSaude.objects.select_related("unidade", "profissional", "especialidade", "sala", "aluno").filter(
        unidade_id__in=unidades_qs.values_list("id", flat=True)
    )
    obj = get_object_or_404(qs, pk=pk)

    can_manage = can(request.user, "saude.manage")
    actions = [{"label": "Voltar", "url": reverse("saude:agenda_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if can_manage:
        actions.append({"label": "Editar", "url": reverse("saude:agenda_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})

    fields = [
        {"label": "Paciente", "value": obj.paciente_nome},
        {"label": "Aluno vinculado", "value": getattr(obj.aluno, "nome", "—") if obj.aluno_id else "—"},
        {"label": "Profissional", "value": getattr(obj.profissional, "nome", "—")},
        {"label": "Unidade", "value": getattr(obj.unidade, "nome", "—")},
        {"label": "Especialidade", "value": getattr(obj.especialidade, "nome", "—") if obj.especialidade_id else "—"},
        {"label": "Sala", "value": getattr(obj.sala, "nome", "—") if obj.sala_id else "—"},
        {"label": "Início", "value": obj.inicio.strftime("%d/%m/%Y %H:%M")},
        {"label": "Fim", "value": obj.fim.strftime("%d/%m/%Y %H:%M")},
        {"label": "Motivo", "value": obj.motivo or "—"},
    ]
    pills = [{"label": "Status", "value": obj.get_status_display(), "variant": "info"}]

    return render(request, "saude/agenda_detail.html", {"obj": obj, "fields": fields, "pills": pills, "actions": actions})
