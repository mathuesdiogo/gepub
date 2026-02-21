from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import can

from .forms_periodos import PeriodoLetivoForm
from .models_periodos import PeriodoLetivo
from datetime import date

@login_required
@require_perm("educacao.view")
def periodo_list(request):
    q = (request.GET.get("q") or "").strip()
    ano = (request.GET.get("ano") or "").strip()

    qs = PeriodoLetivo.objects.all()

    if ano.isdigit():
        qs = qs.filter(ano_letivo=int(ano))

    if q:
        qs = qs.filter(
            Q(tipo__icontains=q)
            | Q(numero__icontains=q)
        )

    qs = qs.order_by("-ano_letivo", "tipo", "numero")

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    can_manage = can(request.user, "educacao.manage")

    # actions
    qs_query = []
    if q:
        qs_query.append(f"q={q}")
    if ano:
        qs_query.append(f"ano={ano}")
    base_query = "&".join(qs_query)

    actions = []

    if can_manage:
        actions.append({
            "label": "Gerar 4 Bimestres",
            "url": reverse("educacao:periodo_gerar_bimestres") + f"?ano={ano or ''}",
            "icon": "fa-solid fa-wand-magic-sparkles",
            "variant": "btn--ghost",
        })
        actions.append({
            "label": "Novo Período",
            "url": reverse("educacao:periodo_create"),
            "icon": "fa-solid fa-plus",
            "variant": "btn-primary",
        })


    headers = [
        {"label": "Ano", "width": "110px"},
        {"label": "Tipo", "width": "140px"},
        {"label": "Nº", "width": "90px"},
        {"label": "Início", "width": "140px"},
        {"label": "Fim", "width": "140px"},
        {"label": "Ativo", "width": "110px"},
    ]

    rows = []
    for p in page_obj:
        rows.append({
            "cells": [
                {"text": str(p.ano_letivo)},
                {"text": p.get_tipo_display()},
                {"text": str(p.numero)},
                {"text": p.inicio.strftime("%d/%m/%Y") if p.inicio else "—"},
                {"text": p.fim.strftime("%d/%m/%Y") if p.fim else "—"},
                {"text": "Sim" if p.ativo else "Não"},
            ],
            "can_edit": bool(can_manage),
            "edit_url": reverse("educacao:periodo_update", args=[p.pk]) if can_manage else "",
        })

    extra_filters = f"""
      <div class="filter-bar__field">
        <label class="small">Ano letivo</label>
        <input name="ano" value="{ano}" placeholder="Ex.: 2026" />
      </div>
    """

    return render(request, "educacao/periodo_list.html", {
        "q": q,
        "ano": ano,
        "page_obj": page_obj,
        "actions": actions,
        "headers": headers,
        "rows": rows,
        "action_url": reverse("educacao:periodo_list"),
        "clear_url": reverse("educacao:periodo_list"),
        "has_filters": bool(ano),
        "extra_filters": extra_filters,
    })


@login_required
@require_perm("educacao.manage")
def periodo_create(request):
    if request.method == "POST":
        form = PeriodoLetivoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Período criado com sucesso.")
            return redirect("educacao:periodo_list")
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = PeriodoLetivoForm()

    return render(request, "educacao/periodo_form.html", {
        "form": form,
        "mode": "create",
        "cancel_url": reverse("educacao:periodo_list"),
        "submit_label": "Salvar",
        "action_url": reverse("educacao:periodo_create"),
    })


@login_required
@require_perm("educacao.manage")
def periodo_update(request, pk: int):
    periodo = get_object_or_404(PeriodoLetivo, pk=pk)

    if request.method == "POST":
        form = PeriodoLetivoForm(request.POST, instance=periodo)
        if form.is_valid():
            form.save()
            messages.success(request, "Período atualizado com sucesso.")
            return redirect("educacao:periodo_list")
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = PeriodoLetivoForm(instance=periodo)

    return render(request, "educacao/periodo_form.html", {
        "form": form,
        "mode": "update",
        "periodo": periodo,
        "cancel_url": reverse("educacao:periodo_list"),
        "submit_label": "Atualizar",
        "action_url": reverse("educacao:periodo_update", args=[periodo.pk]),
    })

@login_required
@require_perm("educacao.manage")
def periodo_gerar_bimestres(request):
    """
    Gera 4 bimestres para um ano letivo com datas padrão.
    Se já existir (ano/tipo/numero), não duplica.
    """
    ano_str = (request.GET.get("ano") or "").strip()
    if not ano_str.isdigit():
        messages.error(request, "Informe o ano letivo para gerar os bimestres. Ex.: ?ano=2026")
        return redirect("educacao:periodo_list")

    ano = int(ano_str)

    # Datas padrão (você pode ajustar depois editando cada período)
    # Padrão comum municipal: fev→dez (com recesso no meio do ano)
    periodos_padrao = [
        (1, date(ano, 2, 1),  date(ano, 4, 30)),
        (2, date(ano, 5, 1),  date(ano, 6, 30)),
        (3, date(ano, 8, 1),  date(ano, 9, 30)),
        (4, date(ano, 10, 1), date(ano, 12, 15)),
    ]

    created = 0
    skipped = 0

    for numero, inicio, fim in periodos_padrao:
        obj, was_created = PeriodoLetivo.objects.get_or_create(
            ano_letivo=ano,
            tipo=PeriodoLetivo.Tipo.BIMESTRE,
            numero=numero,
            defaults={"inicio": inicio, "fim": fim, "ativo": True},
        )
        if was_created:
            created += 1
        else:
            skipped += 1

    if created:
        messages.success(request, f"Bimestres gerados: {created}. (Ignorados por já existir: {skipped})")
    else:
        messages.info(request, f"Nenhum bimestre criado. Já existiam todos os 4 para {ano}.")

    return redirect(f"{reverse('educacao:periodo_list')}?ano={ano}")