from __future__ import annotations

from .views_common import *
from .views_common import _municipios_admin, _resolve_municipio

@login_required
@require_perm("financeiro.tesouraria")
def extrato_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    exercicio = _selected_exercicio(request, municipio)

    qs = (
        TesExtratoImportacao.objects.filter(municipio=municipio)
        .select_related("conta_bancaria", "exercicio")
        .annotate(total_conciliados=Count("itens__conciliacao", distinct=True))
    )
    if exercicio:
        qs = qs.filter(exercicio=exercicio)
    if q:
        qs = qs.filter(
            Q(arquivo_nome__icontains=q)
            | Q(conta_bancaria__banco_nome__icontains=q)
            | Q(conta_bancaria__conta__icontains=q)
        )

    return render(
        request,
        "financeiro/extrato_list.html",
        {
            "title": "Conciliação bancária",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-criado_em", "-id"),
            "q": q,
            "exercicio": exercicio,
            "exercicios": FinanceiroExercicio.objects.filter(municipio=municipio).order_by("-ano"),
            "actions": [
                {
                    "label": "Importar extrato",
                    "url": reverse("financeiro:extrato_create") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-file-import",
                    "variant": "btn-primary",
                },
                {
                    "label": "Voltar",
                    "url": reverse("financeiro:index") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )

@login_required
@require_perm("financeiro.tesouraria")
def extrato_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para importar extrato.")
        return redirect("financeiro:extrato_list")

    form = TesExtratoImportacaoUploadForm(request.POST or None, request.FILES or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        arquivo = form.cleaned_data["arquivo"]
        try:
            importacao = importar_extrato_bancario(
                municipio=municipio,
                exercicio=form.cleaned_data["exercicio"],
                conta_bancaria=form.cleaned_data["conta_bancaria"],
                formato=form.cleaned_data["formato"],
                arquivo_nome=arquivo.name,
                raw_bytes=arquivo.read(),
                usuario=request.user,
                observacao=form.cleaned_data.get("observacao") or "",
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Extrato importado com sucesso.")
            return redirect(reverse("financeiro:extrato_detail", args=[importacao.pk]) + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Importar extrato bancário",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "enctype": "multipart/form-data",
            "cancel_url": reverse("financeiro:extrato_list") + f"?municipio={municipio.pk}",
            "submit_label": "Importar extrato",
        },
    )

@login_required
@require_perm("financeiro.tesouraria")
def extrato_detail(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    importacao = get_object_or_404(
        TesExtratoImportacao.objects.select_related("conta_bancaria", "exercicio"),
        pk=pk,
        municipio=municipio,
    )
    q = (request.GET.get("q") or "").strip()

    itens_qs = TesExtratoItem.objects.filter(importacao=importacao).select_related(
        "conciliacao",
        "conciliacao__receita",
        "conciliacao__desp_pagamento",
        "conciliacao__desp_pagamento_resto",
    )
    if q:
        q_filter = (
            Q(documento__icontains=q)
            | Q(historico__icontains=q)
            | Q(identificador_externo__icontains=q)
        )
        try:
            q_value = Decimal(q.replace(",", "."))
        except Exception:
            q_value = None
        if q_value is not None:
            q_filter = q_filter | Q(valor=q_value)
        itens_qs = itens_qs.filter(q_filter)

    total_conciliados = RecConciliacaoItem.objects.filter(extrato_item__importacao=importacao).count()
    total_pendentes = max(importacao.total_itens - total_conciliados, 0)

    return render(
        request,
        "financeiro/extrato_detail.html",
        {
            "title": f"Extrato {importacao.formato} • {importacao.conta_bancaria.banco_nome}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "importacao": importacao,
            "items": itens_qs.order_by("data_movimento", "id"),
            "q": q,
            "total_conciliados": total_conciliados,
            "total_pendentes": total_pendentes,
            "actions": [
                {
                    "label": "Conciliação automática",
                    "url": reverse("financeiro:extrato_auto", args=[importacao.pk]) + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-wand-magic-sparkles",
                    "variant": "btn-primary",
                },
                {
                    "label": "Voltar",
                    "url": reverse("financeiro:extrato_list") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )

@login_required
@require_perm("financeiro.tesouraria")
def extrato_auto(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    importacao = get_object_or_404(TesExtratoImportacao, pk=pk, municipio=municipio)
    result = executar_conciliacao_automatica(importacao, usuario=request.user)
    messages.success(
        request,
        (
            "Conciliação automática concluída: "
            f"{result['conciliados']} itens conciliados "
            f"(receitas: {result['receitas']}, pagamentos: {result['pagamentos']}, RP: {result['pagamentos_rp']})."
        ),
    )
    return redirect(reverse("financeiro:extrato_detail", args=[importacao.pk]) + f"?municipio={municipio.pk}")

@login_required
@require_perm("financeiro.tesouraria")
def extrato_ajuste(request, item_pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    item = get_object_or_404(TesExtratoItem.objects.select_related("importacao"), pk=item_pk, municipio=municipio)
    next_url = (request.GET.get("next") or "").strip()

    form = RecConciliacaoAjusteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        marcar_item_como_ajuste(item, usuario=request.user, observacao=form.cleaned_data.get("observacao") or "")
        messages.success(request, "Item conciliado manualmente como ajuste.")
        if next_url:
            return redirect(next_url)
        return redirect(reverse("financeiro:extrato_detail", args=[item.importacao_id]) + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Conciliar item como ajuste",
            "subtitle": f"{item.data_movimento:%d/%m/%Y} • {item.historico or 'Sem histórico'} • {item.valor}",
            "actions": [],
            "form": form,
            "cancel_url": next_url or reverse("financeiro:extrato_detail", args=[item.importacao_id]) + f"?municipio={municipio.pk}",
            "submit_label": "Confirmar ajuste",
        },
    )

@login_required
@require_perm("financeiro.tesouraria")
def extrato_desfazer(request, item_pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    item = get_object_or_404(TesExtratoItem.objects.select_related("importacao"), pk=item_pk, municipio=municipio)
    desfazer_conciliacao(item, usuario=request.user)
    messages.success(request, "Conciliação desfeita com sucesso.")
    return redirect(reverse("financeiro:extrato_detail", args=[item.importacao_id]) + f"?municipio={municipio.pk}")
