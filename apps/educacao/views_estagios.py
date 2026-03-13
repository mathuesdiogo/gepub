from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from apps.core.decorators import require_perm
from apps.core.rbac import can, scope_filter_unidades
from apps.org.models import Unidade

from .forms_estagios import EstagioForm
from .models import Estagio


def _unidades_escopo(user):
    return scope_filter_unidades(
        user,
        Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO, ativo=True).select_related("secretaria", "secretaria__municipio"),
    )


def _estagios_scope(user):
    unidades_qs = _unidades_escopo(user)
    qs = (
        Estagio.objects.select_related(
            "aluno",
            "matricula",
            "turma",
            "unidade",
            "unidade__secretaria",
            "unidade__secretaria__municipio",
            "orientador",
            "cadastrado_por",
            "atualizado_por",
        )
        .filter(unidade__in=unidades_qs)
        .order_by("-criado_em", "-id")
    )
    return qs, unidades_qs


@login_required
@require_perm("educacao.view")
def estagio_list(request):
    q = (request.GET.get("q") or "").strip()
    tipo = (request.GET.get("tipo") or "").strip()
    situacao = (request.GET.get("situacao") or "").strip()
    can_manage = can(request.user, "educacao.manage")

    qs, _ = _estagios_scope(request.user)
    if q:
        filters = (
            Q(aluno__nome__icontains=q)
            | Q(concedente_nome__icontains=q)
            | Q(concedente_cnpj__icontains=q)
            | Q(supervisor_nome__icontains=q)
            | Q(observacao__icontains=q)
        )
        if q.isdigit():
            filters |= Q(id=int(q)) | Q(matricula_id=int(q))
        qs = qs.filter(filters)
    if tipo in {choice for choice, _ in Estagio.Tipo.choices}:
        qs = qs.filter(tipo=tipo)
    if situacao in {choice for choice, _ in Estagio.Situacao.choices}:
        qs = qs.filter(situacao=situacao)

    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))

    rows = []
    for estagio in page_obj:
        rows.append(
            {
                "cells": [
                    {"text": estagio.aluno.nome, "url": reverse("educacao:estagio_detail", args=[estagio.pk])},
                    {"text": estagio.get_tipo_display()},
                    {"text": estagio.get_situacao_display()},
                    {"text": estagio.unidade.nome},
                    {"text": estagio.concedente_nome},
                    {"text": str(estagio.carga_horaria_total or 0)},
                    {"text": str(estagio.carga_horaria_cumprida or 0)},
                    {"text": "Sim" if estagio.equivalencia_aprovada else "Não"},
                    {"text": "Sim" if estagio.ativo else "Não"},
                ],
                "can_edit": can_manage,
                "edit_url": reverse("educacao:estagio_update", args=[estagio.pk]) if can_manage else "",
            }
        )

    actions = [
        {
            "label": "Voltar",
            "url": reverse("educacao:index"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        },
    ]
    if can_manage:
        actions.insert(
            0,
            {
                "label": "Novo Estágio",
                "url": reverse("educacao:estagio_create"),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            },
        )

    tipo_options = format_html_join(
        "",
        '<option value="{}"{}>{}</option>',
        ((value, " selected" if tipo == value else "", label) for value, label in Estagio.Tipo.choices),
    )
    situacao_options = format_html_join(
        "",
        '<option value="{}"{}>{}</option>',
        ((value, " selected" if situacao == value else "", label) for value, label in Estagio.Situacao.choices),
    )
    extra_filters = str(
        format_html(
            (
                '<div class="filter-bar__field"><label class="small">Tipo</label><select name="tipo">'
                '<option value="">Todos</option>{}</select></div>'
                '<div class="filter-bar__field"><label class="small">Situação</label><select name="situacao">'
                '<option value="">Todas</option>{}</select></div>'
            ),
            tipo_options,
            situacao_options,
        )
    )

    return render(
        request,
        "educacao/estagio_list.html",
        {
            "q": q,
            "tipo": tipo,
            "situacao": situacao,
            "actions": actions,
            "headers": [
                {"label": "Aluno"},
                {"label": "Tipo", "width": "130px"},
                {"label": "Situação", "width": "140px"},
                {"label": "Unidade"},
                {"label": "Concedente"},
                {"label": "CH Total", "width": "90px"},
                {"label": "CH Cumprida", "width": "100px"},
                {"label": "Equiv. Aprov.", "width": "110px"},
                {"label": "Ativo", "width": "80px"},
            ],
            "rows": rows,
            "page_obj": page_obj,
            "action_url": reverse("educacao:estagio_list"),
            "clear_url": reverse("educacao:estagio_list"),
            "extra_filters": extra_filters,
            "has_filters": bool(tipo or situacao),
        },
    )


@login_required
@require_perm("educacao.view")
def estagio_detail(request, pk: int):
    qs, _ = _estagios_scope(request.user)
    estagio = get_object_or_404(qs, pk=pk)
    can_manage = can(request.user, "educacao.manage")

    actions = [
        {
            "label": "Voltar",
            "url": reverse("educacao:estagio_list"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }
    ]
    if can_manage:
        actions.append(
            {
                "label": "Editar",
                "url": reverse("educacao:estagio_update", args=[estagio.pk]),
                "icon": "fa-solid fa-pen",
                "variant": "btn-primary",
            }
        )

    fields = [
        {"label": "Aluno", "value": estagio.aluno.nome},
        {"label": "Matrícula", "value": estagio.matricula_id or "—"},
        {"label": "Turma", "value": str(estagio.turma) if estagio.turma_id else "—"},
        {"label": "Unidade", "value": estagio.unidade.nome},
        {"label": "Tipo", "value": estagio.get_tipo_display()},
        {"label": "Situação", "value": estagio.get_situacao_display()},
        {"label": "Concedente", "value": estagio.concedente_nome},
        {"label": "CNPJ concedente", "value": estagio.concedente_cnpj or "—"},
        {"label": "Supervisor", "value": estagio.supervisor_nome or "—"},
        {"label": "Orientador", "value": estagio.orientador.username if estagio.orientador_id else "—"},
        {
            "label": "Período previsto",
            "value": f"{estagio.data_inicio_prevista:%d/%m/%Y} a {estagio.data_fim_prevista:%d/%m/%Y}"
            if estagio.data_inicio_prevista and estagio.data_fim_prevista
            else "—",
        },
        {
            "label": "Período real",
            "value": f"{estagio.data_inicio_real:%d/%m/%Y} a {estagio.data_fim_real:%d/%m/%Y}"
            if estagio.data_inicio_real and estagio.data_fim_real
            else "—",
        },
        {"label": "Carga horária total", "value": estagio.carga_horaria_total},
        {"label": "Carga horária cumprida", "value": estagio.carga_horaria_cumprida},
        {"label": "Equivalência solicitada", "value": "Sim" if estagio.equivalencia_solicitada else "Não"},
        {"label": "Equivalência aprovada", "value": "Sim" if estagio.equivalencia_aprovada else "Não"},
        {"label": "Termo de compromisso", "value": estagio.termo_compromisso.name if estagio.termo_compromisso else "—"},
        {"label": "Relatório final", "value": estagio.relatorio_final.name if estagio.relatorio_final else "—"},
        {"label": "Observações", "value": estagio.observacao or "—"},
        {"label": "Status ativo", "value": "Sim" if estagio.ativo else "Não"},
    ]
    pills = [
        {"label": "Criado em", "value": estagio.criado_em.strftime("%d/%m/%Y %H:%M")},
        {"label": "Atualizado em", "value": estagio.atualizado_em.strftime("%d/%m/%Y %H:%M")},
    ]

    return render(
        request,
        "educacao/estagio_detail.html",
        {
            "estagio": estagio,
            "actions": actions,
            "fields": fields,
            "pills": pills,
        },
    )


@login_required
@require_perm("educacao.manage")
def estagio_create(request):
    form = EstagioForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == "POST":
        if form.is_valid():
            obj = form.save(commit=False)
            obj.cadastrado_por = request.user
            obj.atualizado_por = request.user
            obj.save()
            messages.success(request, "Estágio registrado com sucesso.")
            return redirect("educacao:estagio_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")

    return render(
        request,
        "educacao/estagio_form.html",
        {
            "form": form,
            "mode": "create",
            "cancel_url": reverse("educacao:estagio_list"),
            "submit_label": "Salvar estágio",
            "action_url": reverse("educacao:estagio_create"),
        },
    )


@login_required
@require_perm("educacao.manage")
def estagio_update(request, pk: int):
    qs, _ = _estagios_scope(request.user)
    estagio = get_object_or_404(qs, pk=pk)
    form = EstagioForm(request.POST or None, request.FILES or None, instance=estagio, user=request.user)
    if request.method == "POST":
        if form.is_valid():
            obj = form.save(commit=False)
            obj.atualizado_por = request.user
            obj.save()
            messages.success(request, "Estágio atualizado com sucesso.")
            return redirect("educacao:estagio_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")

    return render(
        request,
        "educacao/estagio_form.html",
        {
            "form": form,
            "mode": "update",
            "estagio": estagio,
            "cancel_url": reverse("educacao:estagio_list"),
            "submit_label": "Atualizar estágio",
            "action_url": reverse("educacao:estagio_update", args=[estagio.pk]),
        },
    )
