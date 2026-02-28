from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import can, scope_filter_unidades
from apps.org.models import Unidade

from .forms import EncaminhamentoSaudeForm, ProcedimentoSaudeForm, VacinacaoSaudeForm
from .models import (
    AtendimentoSaude,
    EncaminhamentoSaude,
    ProcedimentoSaude,
    ProfissionalSaude,
    VacinacaoSaude,
)


def _scoped_unidades(user):
    return scope_filter_unidades(user, Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE).order_by("nome"))


def _scoped_profissionais(unidades_qs):
    return ProfissionalSaude.objects.filter(unidade_id__in=unidades_qs.values_list("id", flat=True), ativo=True).order_by("nome")


def _scoped_atendimentos(unidades_qs):
    return AtendimentoSaude.objects.filter(unidade_id__in=unidades_qs.values_list("id", flat=True)).order_by("-data", "-id")


@login_required
@require_perm("saude.view")
def procedimento_list(request):
    q = (request.GET.get("q") or "").strip()
    unidades_qs = _scoped_unidades(request.user)
    qs = ProcedimentoSaude.objects.select_related("atendimento", "atendimento__unidade").filter(
        atendimento__unidade_id__in=unidades_qs.values_list("id", flat=True)
    )
    if q:
        qs = qs.filter(
            Q(descricao__icontains=q)
            | Q(atendimento__paciente_nome__icontains=q)
            | Q(atendimento__unidade__nome__icontains=q)
        )

    page_obj = Paginator(qs.order_by("-realizado_em", "-id"), 10).get_page(request.GET.get("page"))
    can_manage = can(request.user, "saude.manage")
    actions = []
    if can_manage:
        actions.append({"label": "Novo Procedimento", "url": reverse("saude:procedimento_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})

    headers = [{"label": "Paciente"}, {"label": "Procedimento"}, {"label": "Data/Hora"}, {"label": "Unidade"}]
    rows = []
    for obj in page_obj:
        rows.append(
            {
                "cells": [
                    {"text": obj.atendimento.paciente_nome, "url": reverse("saude:procedimento_detail", args=[obj.pk])},
                    {"text": f"{obj.get_tipo_display()} • {obj.descricao}"},
                    {"text": obj.realizado_em.strftime("%d/%m/%Y %H:%M")},
                    {"text": obj.atendimento.unidade.nome},
                ],
                "can_edit": bool(can_manage),
                "edit_url": reverse("saude:procedimento_update", args=[obj.pk]) if can_manage else "",
            }
        )

    return render(
        request,
        "saude/procedimento_list.html",
        {
            "q": q,
            "page_obj": page_obj,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "action_url": reverse("saude:procedimento_list"),
            "clear_url": reverse("saude:procedimento_list"),
            "has_filters": False,
        },
    )


@login_required
@require_perm("saude.manage")
def procedimento_create(request):
    unidades_qs = _scoped_unidades(request.user)
    if request.method == "POST":
        form = ProcedimentoSaudeForm(request.POST, unidades_qs=unidades_qs)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.criado_por = request.user
            obj.save()
            messages.success(request, "Procedimento registrado com sucesso.")
            return redirect("saude:procedimento_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = ProcedimentoSaudeForm(unidades_qs=unidades_qs)
    return render(
        request,
        "saude/procedimento_form.html",
        {"form": form, "mode": "create", "cancel_url": reverse("saude:procedimento_list"), "submit_label": "Salvar", "action_url": reverse("saude:procedimento_create")},
    )


@login_required
@require_perm("saude.manage")
def procedimento_update(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    obj = get_object_or_404(
        ProcedimentoSaude.objects.select_related("atendimento").filter(
            atendimento__unidade_id__in=unidades_qs.values_list("id", flat=True)
        ),
        pk=pk,
    )
    if request.method == "POST":
        form = ProcedimentoSaudeForm(request.POST, instance=obj, unidades_qs=unidades_qs)
        if form.is_valid():
            form.save()
            messages.success(request, "Procedimento atualizado com sucesso.")
            return redirect("saude:procedimento_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = ProcedimentoSaudeForm(instance=obj, unidades_qs=unidades_qs)
    return render(
        request,
        "saude/procedimento_form.html",
        {"form": form, "mode": "update", "obj": obj, "cancel_url": reverse("saude:procedimento_detail", args=[obj.pk]), "submit_label": "Salvar", "action_url": reverse("saude:procedimento_update", args=[obj.pk])},
    )


@login_required
@require_perm("saude.view")
def procedimento_detail(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    obj = get_object_or_404(
        ProcedimentoSaude.objects.select_related("atendimento", "atendimento__unidade", "criado_por").filter(
            atendimento__unidade_id__in=unidades_qs.values_list("id", flat=True)
        ),
        pk=pk,
    )
    can_manage = can(request.user, "saude.manage")
    actions = [{"label": "Voltar", "url": reverse("saude:procedimento_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if can_manage:
        actions.append({"label": "Editar", "url": reverse("saude:procedimento_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})
    fields = [
        {"label": "Paciente", "value": obj.atendimento.paciente_nome},
        {"label": "Atendimento", "value": f"#{obj.atendimento.id} • {obj.atendimento.get_tipo_display()}"},
        {"label": "Tipo", "value": obj.get_tipo_display()},
        {"label": "Descrição", "value": obj.descricao},
        {"label": "Materiais", "value": obj.materiais or "—"},
        {"label": "Intercorrências", "value": obj.intercorrencias or "—"},
        {"label": "Unidade", "value": obj.atendimento.unidade.nome},
        {"label": "Registrado por", "value": obj.criado_por.get_username()},
    ]
    pills = [{"label": "Realizado em", "value": obj.realizado_em.strftime("%d/%m/%Y %H:%M"), "variant": "info"}]
    return render(request, "saude/procedimento_detail.html", {"obj": obj, "fields": fields, "pills": pills, "actions": actions})


@login_required
@require_perm("saude.view")
def vacinacao_list(request):
    q = (request.GET.get("q") or "").strip()
    unidades_qs = _scoped_unidades(request.user)
    qs = VacinacaoSaude.objects.select_related("atendimento", "unidade_aplicadora", "aplicador").filter(
        unidade_aplicadora_id__in=unidades_qs.values_list("id", flat=True)
    )
    if q:
        qs = qs.filter(Q(vacina__icontains=q) | Q(atendimento__paciente_nome__icontains=q) | Q(lote__icontains=q))

    page_obj = Paginator(qs.order_by("-data_aplicacao", "-id"), 10).get_page(request.GET.get("page"))
    can_manage = can(request.user, "saude.manage")
    actions = []
    if can_manage:
        actions.append({"label": "Nova Vacinação", "url": reverse("saude:vacinacao_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})

    headers = [{"label": "Paciente"}, {"label": "Vacina"}, {"label": "Dose/Lote"}, {"label": "Aplicação"}]
    rows = []
    for obj in page_obj:
        rows.append(
            {
                "cells": [
                    {"text": obj.atendimento.paciente_nome, "url": reverse("saude:vacinacao_detail", args=[obj.pk])},
                    {"text": obj.vacina},
                    {"text": f"{obj.dose or '—'} / {obj.lote or '—'}"},
                    {"text": f"{obj.data_aplicacao:%d/%m/%Y} • {obj.unidade_aplicadora.nome}"},
                ],
                "can_edit": bool(can_manage),
                "edit_url": reverse("saude:vacinacao_update", args=[obj.pk]) if can_manage else "",
            }
        )

    return render(
        request,
        "saude/vacinacao_list.html",
        {
            "q": q,
            "page_obj": page_obj,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "action_url": reverse("saude:vacinacao_list"),
            "clear_url": reverse("saude:vacinacao_list"),
            "has_filters": False,
        },
    )


@login_required
@require_perm("saude.manage")
def vacinacao_create(request):
    unidades_qs = _scoped_unidades(request.user)
    profissionais_qs = _scoped_profissionais(unidades_qs)
    if request.method == "POST":
        form = VacinacaoSaudeForm(request.POST, unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.criado_por = request.user
            obj.save()
            messages.success(request, "Vacinação registrada com sucesso.")
            return redirect("saude:vacinacao_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = VacinacaoSaudeForm(unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)
    return render(
        request,
        "saude/vacinacao_form.html",
        {"form": form, "mode": "create", "cancel_url": reverse("saude:vacinacao_list"), "submit_label": "Salvar", "action_url": reverse("saude:vacinacao_create")},
    )


@login_required
@require_perm("saude.manage")
def vacinacao_update(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    profissionais_qs = _scoped_profissionais(unidades_qs)
    obj = get_object_or_404(
        VacinacaoSaude.objects.select_related("unidade_aplicadora").filter(
            unidade_aplicadora_id__in=unidades_qs.values_list("id", flat=True)
        ),
        pk=pk,
    )
    if request.method == "POST":
        form = VacinacaoSaudeForm(request.POST, instance=obj, unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)
        if form.is_valid():
            form.save()
            messages.success(request, "Vacinação atualizada com sucesso.")
            return redirect("saude:vacinacao_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = VacinacaoSaudeForm(instance=obj, unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)
    return render(
        request,
        "saude/vacinacao_form.html",
        {"form": form, "mode": "update", "obj": obj, "cancel_url": reverse("saude:vacinacao_detail", args=[obj.pk]), "submit_label": "Salvar", "action_url": reverse("saude:vacinacao_update", args=[obj.pk])},
    )


@login_required
@require_perm("saude.view")
def vacinacao_detail(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    obj = get_object_or_404(
        VacinacaoSaude.objects.select_related("atendimento", "unidade_aplicadora", "aplicador", "criado_por").filter(
            unidade_aplicadora_id__in=unidades_qs.values_list("id", flat=True)
        ),
        pk=pk,
    )
    can_manage = can(request.user, "saude.manage")
    actions = [{"label": "Voltar", "url": reverse("saude:vacinacao_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if can_manage:
        actions.append({"label": "Editar", "url": reverse("saude:vacinacao_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})
    fields = [
        {"label": "Paciente", "value": obj.atendimento.paciente_nome},
        {"label": "Vacina", "value": obj.vacina},
        {"label": "Dose", "value": obj.dose or "—"},
        {"label": "Lote", "value": obj.lote or "—"},
        {"label": "Fabricante", "value": obj.fabricante or "—"},
        {"label": "Unidade Aplicadora", "value": obj.unidade_aplicadora.nome},
        {"label": "Aplicador", "value": obj.aplicador.nome if obj.aplicador_id else "—"},
        {"label": "Reações", "value": obj.reacoes or "—"},
    ]
    pills = [{"label": "Data de aplicação", "value": obj.data_aplicacao.strftime("%d/%m/%Y"), "variant": "info"}]
    return render(request, "saude/vacinacao_detail.html", {"obj": obj, "fields": fields, "pills": pills, "actions": actions})


@login_required
@require_perm("saude.view")
def encaminhamento_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    unidades_qs = _scoped_unidades(request.user)
    qs = EncaminhamentoSaude.objects.select_related(
        "atendimento",
        "unidade_origem",
        "unidade_destino",
        "especialidade_destino",
    ).filter(unidade_origem_id__in=unidades_qs.values_list("id", flat=True))
    if q:
        qs = qs.filter(
            Q(atendimento__paciente_nome__icontains=q)
            | Q(unidade_origem__nome__icontains=q)
            | Q(unidade_destino__nome__icontains=q)
            | Q(especialidade_destino__nome__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)

    page_obj = Paginator(qs.order_by("-criado_em", "-id"), 10).get_page(request.GET.get("page"))
    can_manage = can(request.user, "saude.manage")
    actions = []
    if can_manage:
        actions.append({"label": "Novo Encaminhamento", "url": reverse("saude:encaminhamento_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})

    headers = [{"label": "Paciente"}, {"label": "Origem"}, {"label": "Destino"}, {"label": "Prioridade"}, {"label": "Status"}]
    rows = []
    for obj in page_obj:
        rows.append(
            {
                "cells": [
                    {"text": obj.atendimento.paciente_nome, "url": reverse("saude:encaminhamento_detail", args=[obj.pk])},
                    {"text": obj.unidade_origem.nome},
                    {"text": obj.unidade_destino.nome if obj.unidade_destino_id else "—"},
                    {"text": obj.get_prioridade_display()},
                    {"text": obj.get_status_display()},
                ],
                "can_edit": bool(can_manage),
                "edit_url": reverse("saude:encaminhamento_update", args=[obj.pk]) if can_manage else "",
            }
        )

    extra_filters = """
      <div class=\"filter-bar__field\">
        <label class=\"small\">Status</label>
        <select name=\"status\">
          <option value=\"\">Todos</option>
    """
    for k, v in EncaminhamentoSaude.Status.choices:
        selected = "selected" if status == k else ""
        extra_filters += f"<option value=\"{k}\" {selected}>{v}</option>"
    extra_filters += """
        </select>
      </div>
    """

    return render(
        request,
        "saude/encaminhamento_list.html",
        {
            "q": q,
            "status": status,
            "page_obj": page_obj,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "action_url": reverse("saude:encaminhamento_list"),
            "clear_url": reverse("saude:encaminhamento_list"),
            "has_filters": bool(status),
            "extra_filters": extra_filters,
        },
    )


@login_required
@require_perm("saude.manage")
def encaminhamento_create(request):
    unidades_qs = _scoped_unidades(request.user)
    atendimentos_qs = _scoped_atendimentos(unidades_qs)
    if request.method == "POST":
        form = EncaminhamentoSaudeForm(request.POST, unidades_qs=unidades_qs)
        form.fields["atendimento"].queryset = atendimentos_qs
        if form.is_valid():
            obj = form.save(commit=False)
            obj.criado_por = request.user
            obj.save()
            messages.success(request, "Encaminhamento registrado com sucesso.")
            return redirect("saude:encaminhamento_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = EncaminhamentoSaudeForm(unidades_qs=unidades_qs)
        form.fields["atendimento"].queryset = atendimentos_qs
    return render(
        request,
        "saude/encaminhamento_form.html",
        {"form": form, "mode": "create", "cancel_url": reverse("saude:encaminhamento_list"), "submit_label": "Salvar", "action_url": reverse("saude:encaminhamento_create")},
    )


@login_required
@require_perm("saude.manage")
def encaminhamento_update(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    atendimentos_qs = _scoped_atendimentos(unidades_qs)
    obj = get_object_or_404(
        EncaminhamentoSaude.objects.select_related("unidade_origem").filter(
            unidade_origem_id__in=unidades_qs.values_list("id", flat=True)
        ),
        pk=pk,
    )
    if request.method == "POST":
        form = EncaminhamentoSaudeForm(request.POST, instance=obj, unidades_qs=unidades_qs)
        form.fields["atendimento"].queryset = atendimentos_qs
        if form.is_valid():
            form.save()
            messages.success(request, "Encaminhamento atualizado com sucesso.")
            return redirect("saude:encaminhamento_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = EncaminhamentoSaudeForm(instance=obj, unidades_qs=unidades_qs)
        form.fields["atendimento"].queryset = atendimentos_qs
    return render(
        request,
        "saude/encaminhamento_form.html",
        {"form": form, "mode": "update", "obj": obj, "cancel_url": reverse("saude:encaminhamento_detail", args=[obj.pk]), "submit_label": "Salvar", "action_url": reverse("saude:encaminhamento_update", args=[obj.pk])},
    )


@login_required
@require_perm("saude.view")
def encaminhamento_detail(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    obj = get_object_or_404(
        EncaminhamentoSaude.objects.select_related(
            "atendimento",
            "unidade_origem",
            "unidade_destino",
            "especialidade_destino",
            "criado_por",
        ).filter(unidade_origem_id__in=unidades_qs.values_list("id", flat=True)),
        pk=pk,
    )
    can_manage = can(request.user, "saude.manage")
    actions = [{"label": "Voltar", "url": reverse("saude:encaminhamento_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if can_manage:
        actions.append({"label": "Editar", "url": reverse("saude:encaminhamento_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})
    fields = [
        {"label": "Paciente", "value": obj.atendimento.paciente_nome},
        {"label": "Unidade origem", "value": obj.unidade_origem.nome},
        {"label": "Unidade destino", "value": obj.unidade_destino.nome if obj.unidade_destino_id else "—"},
        {"label": "Especialidade destino", "value": obj.especialidade_destino.nome if obj.especialidade_destino_id else "—"},
        {"label": "Justificativa", "value": obj.justificativa},
        {"label": "Observações regulação", "value": obj.observacoes_regulacao or "—"},
        {"label": "Criado por", "value": obj.criado_por.get_username()},
    ]
    pills = [
        {"label": "Prioridade", "value": obj.get_prioridade_display(), "variant": "warning"},
        {"label": "Status", "value": obj.get_status_display(), "variant": "info"},
    ]
    return render(request, "saude/encaminhamento_detail.html", {"obj": obj, "fields": fields, "pills": pills, "actions": actions})
