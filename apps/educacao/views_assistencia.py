from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import scope_filter_unidades
from apps.org.models import Unidade

from .forms_assistencia import (
    CardapioEscolarForm,
    RegistroRefeicaoEscolarForm,
    RegistroTransporteEscolarForm,
    RotaTransporteEscolarForm,
)
from .models_assistencia import (
    CardapioEscolar,
    RegistroRefeicaoEscolar,
    RegistroTransporteEscolar,
    RotaTransporteEscolar,
)


def _unidades_escopo(user):
    return scope_filter_unidades(
        user,
        Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO, ativo=True).order_by("nome"),
    )


def _render_list(request, *, title, subtitle, actions, headers, rows, page_obj, q, action_url):
    return render(
        request,
        "educacao/assistencia_list.html",
        {
            "title": title,
            "subtitle": subtitle,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "page_obj": page_obj,
            "q": q,
            "action_url": action_url,
            "clear_url": action_url,
        },
    )


def _render_form(request, *, title, subtitle, form, cancel_url, submit_label, action_url):
    return render(
        request,
        "educacao/assistencia_form.html",
        {
            "title": title,
            "subtitle": subtitle,
            "form": form,
            "cancel_url": cancel_url,
            "submit_label": submit_label,
            "action_url": action_url,
        },
    )


def _render_detail(request, *, title, subtitle, actions, fields):
    return render(
        request,
        "educacao/assistencia_detail.html",
        {
            "title": title,
            "subtitle": subtitle,
            "actions": actions,
            "fields": fields,
        },
    )


@login_required
@require_perm("educacao.view")
def assistencia_index(request):
    unidades_qs = _unidades_escopo(request.user)
    cardapios = CardapioEscolar.objects.filter(unidade__in=unidades_qs)
    refeicoes = RegistroRefeicaoEscolar.objects.filter(unidade__in=unidades_qs)
    rotas = RotaTransporteEscolar.objects.filter(unidade__in=unidades_qs)
    registros_transporte = RegistroTransporteEscolar.objects.filter(rota__unidade__in=unidades_qs)

    return render(
        request,
        "educacao/assistencia_index.html",
        {
            "actions": [
                {"label": "Cardápios", "url": reverse("educacao:assist_cardapio_list"), "icon": "fa-solid fa-utensils", "variant": "btn--ghost"},
                {"label": "Refeições", "url": reverse("educacao:assist_refeicao_list"), "icon": "fa-solid fa-bowl-rice", "variant": "btn--ghost"},
                {"label": "Rotas", "url": reverse("educacao:assist_rota_list"), "icon": "fa-solid fa-route", "variant": "btn--ghost"},
                {"label": "Registros de Transporte", "url": reverse("educacao:assist_transporte_registro_list"), "icon": "fa-solid fa-bus", "variant": "btn--ghost"},
            ],
            "total_cardapios": cardapios.count(),
            "total_refeicoes": refeicoes.aggregate(total=Sum("total_servidas")).get("total") or 0,
            "total_rotas": rotas.count(),
            "total_transportados": registros_transporte.aggregate(total=Sum("total_transportados")).get("total") or 0,
        },
    )


@login_required
@require_perm("educacao.view")
def assist_cardapio_list(request):
    q = (request.GET.get("q") or "").strip()
    unidades_qs = _unidades_escopo(request.user)
    qs = CardapioEscolar.objects.select_related("unidade").filter(unidade__in=unidades_qs).order_by("-data", "unidade__nome")
    if q:
        qs = qs.filter(Q(unidade__nome__icontains=q) | Q(descricao__icontains=q))
    page_obj = Paginator(qs, 12).get_page(request.GET.get("page"))

    rows = []
    for obj in page_obj:
        rows.append(
            {
                "cells": [
                    {"text": obj.unidade.nome},
                    {"text": obj.data.strftime("%d/%m/%Y"), "url": reverse("educacao:assist_cardapio_detail", args=[obj.pk])},
                    {"text": obj.get_turno_display()},
                    {"text": "Sim" if obj.ativo else "Não"},
                ],
                "can_edit": True,
                "edit_url": reverse("educacao:assist_cardapio_update", args=[obj.pk]),
            }
        )
    return _render_list(
        request,
        title="Cardápios Escolares",
        subtitle="Planejamento de merenda por unidade/turno",
        actions=[
            {"label": "Assistência", "url": reverse("educacao:assistencia_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Novo Cardápio", "url": reverse("educacao:assist_cardapio_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"},
        ],
        headers=[{"label": "Unidade"}, {"label": "Data", "width": "130px"}, {"label": "Turno", "width": "120px"}, {"label": "Ativo", "width": "100px"}],
        rows=rows,
        page_obj=page_obj,
        q=q,
        action_url=reverse("educacao:assist_cardapio_list"),
    )


@login_required
@require_perm("educacao.manage")
def assist_cardapio_create(request):
    form = CardapioEscolarForm(request.POST or None)
    form.fields["unidade"].queryset = _unidades_escopo(request.user)
    if request.method == "POST":
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Cardápio criado com sucesso.")
            return redirect("educacao:assist_cardapio_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    return _render_form(
        request,
        title="Novo Cardápio Escolar",
        subtitle="Cadastro de cardápio por unidade e turno",
        form=form,
        cancel_url=reverse("educacao:assist_cardapio_list"),
        submit_label="Salvar",
        action_url=reverse("educacao:assist_cardapio_create"),
    )


@login_required
@require_perm("educacao.manage")
def assist_cardapio_update(request, pk: int):
    unidades_qs = _unidades_escopo(request.user)
    obj = get_object_or_404(CardapioEscolar.objects.filter(unidade__in=unidades_qs), pk=pk)
    form = CardapioEscolarForm(request.POST or None, instance=obj)
    form.fields["unidade"].queryset = unidades_qs
    if request.method == "POST":
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Cardápio atualizado com sucesso.")
            return redirect("educacao:assist_cardapio_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    return _render_form(
        request,
        title="Editar Cardápio Escolar",
        subtitle=f"{obj.unidade.nome} • {obj.data:%d/%m/%Y}",
        form=form,
        cancel_url=reverse("educacao:assist_cardapio_list"),
        submit_label="Atualizar",
        action_url=reverse("educacao:assist_cardapio_update", args=[obj.pk]),
    )


@login_required
@require_perm("educacao.view")
def assist_cardapio_detail(request, pk: int):
    obj = get_object_or_404(CardapioEscolar.objects.select_related("unidade"), pk=pk)
    return _render_detail(
        request,
        title="Detalhe do Cardápio Escolar",
        subtitle=f"{obj.unidade.nome} • {obj.data:%d/%m/%Y}",
        actions=[
            {"label": "Voltar", "url": reverse("educacao:assist_cardapio_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Editar", "url": reverse("educacao:assist_cardapio_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"},
        ],
        fields=[
            {"label": "Unidade", "value": obj.unidade.nome},
            {"label": "Data", "value": obj.data.strftime("%d/%m/%Y")},
            {"label": "Turno", "value": obj.get_turno_display()},
            {"label": "Descrição", "value": obj.descricao},
            {"label": "Observação", "value": obj.observacao or "—"},
            {"label": "Ativo", "value": "Sim" if obj.ativo else "Não"},
        ],
    )


@login_required
@require_perm("educacao.view")
def assist_refeicao_list(request):
    q = (request.GET.get("q") or "").strip()
    unidades_qs = _unidades_escopo(request.user)
    qs = RegistroRefeicaoEscolar.objects.select_related("unidade").filter(unidade__in=unidades_qs).order_by("-data", "unidade__nome")
    if q:
        qs = qs.filter(Q(unidade__nome__icontains=q) | Q(observacao__icontains=q))
    page_obj = Paginator(qs, 12).get_page(request.GET.get("page"))
    rows = []
    for obj in page_obj:
        rows.append(
            {
                "cells": [
                    {"text": obj.unidade.nome},
                    {"text": obj.data.strftime("%d/%m/%Y"), "url": reverse("educacao:assist_refeicao_detail", args=[obj.pk])},
                    {"text": obj.get_turno_display()},
                    {"text": str(obj.total_servidas)},
                ],
                "can_edit": True,
                "edit_url": reverse("educacao:assist_refeicao_update", args=[obj.pk]),
            }
        )
    return _render_list(
        request,
        title="Refeições Servidas",
        subtitle="Registro diário de refeições por unidade",
        actions=[
            {"label": "Assistência", "url": reverse("educacao:assistencia_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Novo Registro", "url": reverse("educacao:assist_refeicao_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"},
        ],
        headers=[{"label": "Unidade"}, {"label": "Data", "width": "130px"}, {"label": "Turno", "width": "120px"}, {"label": "Total", "width": "100px"}],
        rows=rows,
        page_obj=page_obj,
        q=q,
        action_url=reverse("educacao:assist_refeicao_list"),
    )


@login_required
@require_perm("educacao.manage")
def assist_refeicao_create(request):
    form = RegistroRefeicaoEscolarForm(request.POST or None)
    form.fields["unidade"].queryset = _unidades_escopo(request.user)
    if request.method == "POST":
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Registro de refeição criado com sucesso.")
            return redirect("educacao:assist_refeicao_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    return _render_form(
        request,
        title="Novo Registro de Refeição",
        subtitle="Quantidade de refeições servidas por turno",
        form=form,
        cancel_url=reverse("educacao:assist_refeicao_list"),
        submit_label="Salvar",
        action_url=reverse("educacao:assist_refeicao_create"),
    )


@login_required
@require_perm("educacao.manage")
def assist_refeicao_update(request, pk: int):
    unidades_qs = _unidades_escopo(request.user)
    obj = get_object_or_404(RegistroRefeicaoEscolar.objects.filter(unidade__in=unidades_qs), pk=pk)
    form = RegistroRefeicaoEscolarForm(request.POST or None, instance=obj)
    form.fields["unidade"].queryset = unidades_qs
    if request.method == "POST":
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Registro de refeição atualizado com sucesso.")
            return redirect("educacao:assist_refeicao_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    return _render_form(
        request,
        title="Editar Registro de Refeição",
        subtitle=f"{obj.unidade.nome} • {obj.data:%d/%m/%Y}",
        form=form,
        cancel_url=reverse("educacao:assist_refeicao_list"),
        submit_label="Atualizar",
        action_url=reverse("educacao:assist_refeicao_update", args=[obj.pk]),
    )


@login_required
@require_perm("educacao.view")
def assist_refeicao_detail(request, pk: int):
    obj = get_object_or_404(RegistroRefeicaoEscolar.objects.select_related("unidade"), pk=pk)
    return _render_detail(
        request,
        title="Detalhe do Registro de Refeição",
        subtitle=f"{obj.unidade.nome} • {obj.data:%d/%m/%Y}",
        actions=[
            {"label": "Voltar", "url": reverse("educacao:assist_refeicao_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Editar", "url": reverse("educacao:assist_refeicao_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"},
        ],
        fields=[
            {"label": "Unidade", "value": obj.unidade.nome},
            {"label": "Data", "value": obj.data.strftime("%d/%m/%Y")},
            {"label": "Turno", "value": obj.get_turno_display()},
            {"label": "Total servidas", "value": obj.total_servidas},
            {"label": "Observação", "value": obj.observacao or "—"},
        ],
    )


@login_required
@require_perm("educacao.view")
def assist_rota_list(request):
    q = (request.GET.get("q") or "").strip()
    unidades_qs = _unidades_escopo(request.user)
    qs = RotaTransporteEscolar.objects.select_related("unidade").filter(unidade__in=unidades_qs).order_by("unidade__nome", "nome")
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(unidade__nome__icontains=q) | Q(motorista__icontains=q))
    page_obj = Paginator(qs, 12).get_page(request.GET.get("page"))
    rows = []
    for obj in page_obj:
        rows.append(
            {
                "cells": [
                    {"text": obj.unidade.nome},
                    {"text": obj.nome, "url": reverse("educacao:assist_rota_detail", args=[obj.pk])},
                    {"text": obj.get_turno_display()},
                    {"text": obj.veiculo or "—"},
                    {"text": "Sim" if obj.ativo else "Não"},
                ],
                "can_edit": True,
                "edit_url": reverse("educacao:assist_rota_update", args=[obj.pk]),
            }
        )
    return _render_list(
        request,
        title="Rotas de Transporte Escolar",
        subtitle="Gestão de rotas, veículos e motoristas",
        actions=[
            {"label": "Assistência", "url": reverse("educacao:assistencia_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Nova Rota", "url": reverse("educacao:assist_rota_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"},
        ],
        headers=[{"label": "Unidade"}, {"label": "Rota"}, {"label": "Turno", "width": "120px"}, {"label": "Veículo"}, {"label": "Ativo", "width": "100px"}],
        rows=rows,
        page_obj=page_obj,
        q=q,
        action_url=reverse("educacao:assist_rota_list"),
    )


@login_required
@require_perm("educacao.manage")
def assist_rota_create(request):
    form = RotaTransporteEscolarForm(request.POST or None)
    form.fields["unidade"].queryset = _unidades_escopo(request.user)
    if request.method == "POST":
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Rota criada com sucesso.")
            return redirect("educacao:assist_rota_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    return _render_form(
        request,
        title="Nova Rota de Transporte",
        subtitle="Cadastro de rota/veículo/motorista",
        form=form,
        cancel_url=reverse("educacao:assist_rota_list"),
        submit_label="Salvar",
        action_url=reverse("educacao:assist_rota_create"),
    )


@login_required
@require_perm("educacao.manage")
def assist_rota_update(request, pk: int):
    unidades_qs = _unidades_escopo(request.user)
    obj = get_object_or_404(RotaTransporteEscolar.objects.filter(unidade__in=unidades_qs), pk=pk)
    form = RotaTransporteEscolarForm(request.POST or None, instance=obj)
    form.fields["unidade"].queryset = unidades_qs
    if request.method == "POST":
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Rota atualizada com sucesso.")
            return redirect("educacao:assist_rota_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    return _render_form(
        request,
        title="Editar Rota de Transporte",
        subtitle=f"{obj.nome} • {obj.unidade.nome}",
        form=form,
        cancel_url=reverse("educacao:assist_rota_list"),
        submit_label="Atualizar",
        action_url=reverse("educacao:assist_rota_update", args=[obj.pk]),
    )


@login_required
@require_perm("educacao.view")
def assist_rota_detail(request, pk: int):
    obj = get_object_or_404(RotaTransporteEscolar.objects.select_related("unidade"), pk=pk)
    return _render_detail(
        request,
        title="Detalhe da Rota de Transporte",
        subtitle=f"{obj.nome} • {obj.unidade.nome}",
        actions=[
            {"label": "Voltar", "url": reverse("educacao:assist_rota_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Editar", "url": reverse("educacao:assist_rota_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"},
        ],
        fields=[
            {"label": "Unidade", "value": obj.unidade.nome},
            {"label": "Nome", "value": obj.nome},
            {"label": "Turno", "value": obj.get_turno_display()},
            {"label": "Veículo", "value": obj.veiculo or "—"},
            {"label": "Motorista", "value": obj.motorista or "—"},
            {"label": "Ativo", "value": "Sim" if obj.ativo else "Não"},
        ],
    )


@login_required
@require_perm("educacao.view")
def assist_transporte_registro_list(request):
    q = (request.GET.get("q") or "").strip()
    unidades_qs = _unidades_escopo(request.user)
    qs = (
        RegistroTransporteEscolar.objects.select_related("rota", "rota__unidade")
        .filter(rota__unidade__in=unidades_qs)
        .order_by("-data", "rota__nome")
    )
    if q:
        qs = qs.filter(Q(rota__nome__icontains=q) | Q(rota__unidade__nome__icontains=q))
    page_obj = Paginator(qs, 12).get_page(request.GET.get("page"))
    rows = []
    for obj in page_obj:
        rows.append(
            {
                "cells": [
                    {"text": obj.data.strftime("%d/%m/%Y"), "url": reverse("educacao:assist_transporte_registro_detail", args=[obj.pk])},
                    {"text": obj.rota.nome},
                    {"text": obj.rota.unidade.nome},
                    {"text": str(obj.total_previsto)},
                    {"text": str(obj.total_transportados)},
                ],
                "can_edit": True,
                "edit_url": reverse("educacao:assist_transporte_registro_update", args=[obj.pk]),
            }
        )
    return _render_list(
        request,
        title="Registros de Transporte Escolar",
        subtitle="Controle de alunos transportados por rota",
        actions=[
            {"label": "Assistência", "url": reverse("educacao:assistencia_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Novo Registro", "url": reverse("educacao:assist_transporte_registro_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"},
        ],
        headers=[{"label": "Data", "width": "130px"}, {"label": "Rota"}, {"label": "Unidade"}, {"label": "Previsto", "width": "110px"}, {"label": "Transportados", "width": "130px"}],
        rows=rows,
        page_obj=page_obj,
        q=q,
        action_url=reverse("educacao:assist_transporte_registro_list"),
    )


@login_required
@require_perm("educacao.manage")
def assist_transporte_registro_create(request):
    form = RegistroTransporteEscolarForm(request.POST or None)
    form.fields["rota"].queryset = RotaTransporteEscolar.objects.filter(unidade__in=_unidades_escopo(request.user), ativo=True).order_by("nome")
    if request.method == "POST":
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Registro de transporte criado com sucesso.")
            return redirect("educacao:assist_transporte_registro_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    return _render_form(
        request,
        title="Novo Registro de Transporte",
        subtitle="Lançamento diário por rota",
        form=form,
        cancel_url=reverse("educacao:assist_transporte_registro_list"),
        submit_label="Salvar",
        action_url=reverse("educacao:assist_transporte_registro_create"),
    )


@login_required
@require_perm("educacao.manage")
def assist_transporte_registro_update(request, pk: int):
    unidades_qs = _unidades_escopo(request.user)
    obj = get_object_or_404(
        RegistroTransporteEscolar.objects.select_related("rota", "rota__unidade").filter(rota__unidade__in=unidades_qs),
        pk=pk,
    )
    form = RegistroTransporteEscolarForm(request.POST or None, instance=obj)
    form.fields["rota"].queryset = RotaTransporteEscolar.objects.filter(unidade__in=unidades_qs, ativo=True).order_by("nome")
    if request.method == "POST":
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Registro de transporte atualizado com sucesso.")
            return redirect("educacao:assist_transporte_registro_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    return _render_form(
        request,
        title="Editar Registro de Transporte",
        subtitle=f"{obj.rota.nome} • {obj.data:%d/%m/%Y}",
        form=form,
        cancel_url=reverse("educacao:assist_transporte_registro_list"),
        submit_label="Atualizar",
        action_url=reverse("educacao:assist_transporte_registro_update", args=[obj.pk]),
    )


@login_required
@require_perm("educacao.view")
def assist_transporte_registro_detail(request, pk: int):
    obj = get_object_or_404(RegistroTransporteEscolar.objects.select_related("rota", "rota__unidade"), pk=pk)
    return _render_detail(
        request,
        title="Detalhe do Registro de Transporte",
        subtitle=f"{obj.rota.nome} • {obj.data:%d/%m/%Y}",
        actions=[
            {"label": "Voltar", "url": reverse("educacao:assist_transporte_registro_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Editar", "url": reverse("educacao:assist_transporte_registro_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"},
        ],
        fields=[
            {"label": "Data", "value": obj.data.strftime("%d/%m/%Y")},
            {"label": "Rota", "value": obj.rota.nome},
            {"label": "Unidade", "value": obj.rota.unidade.nome},
            {"label": "Total previsto", "value": obj.total_previsto},
            {"label": "Total transportados", "value": obj.total_transportados},
            {"label": "Observação", "value": obj.observacao or "—"},
        ],
    )
