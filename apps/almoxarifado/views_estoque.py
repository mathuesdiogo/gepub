from __future__ import annotations

from django.db.models import Count, F, Sum, Value
from django.db.models.functions import Coalesce

from apps.core.exports import export_csv, export_pdf_table

from .views_common import *
from .views_common import (
    _aplicar_movimento_estoque,
    _apply_scope_filters,
    _municipios_admin,
    _q_municipio,
    _q_scope,
    _resolve_municipio,
    _scope_context,
    _to_dec,
    _parse_date,
)

@login_required
@require_perm("almoxarifado.view")
def index(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    scope_ctx = _scope_context(request, municipio)
    scope_qs = _q_scope(request)
    itens = _apply_scope_filters(
        request,
        AlmoxarifadoCadastro.objects.filter(municipio=municipio),
        secretaria_field="secretaria",
        unidade_field="unidade",
        setor_field="setor",
        local_field="local_estrutural",
    )
    reqs = _apply_scope_filters(
        request,
        AlmoxarifadoRequisicao.objects.filter(municipio=municipio),
        secretaria_field="secretaria_solicitante",
        unidade_field="unidade_solicitante",
        setor_field="setor_solicitante",
        local_field="local_solicitante",
    )
    movs = _apply_scope_filters(
        request,
        AlmoxarifadoMovimento.objects.filter(municipio=municipio),
        secretaria_field="item__secretaria",
        unidade_field="item__unidade",
        setor_field="item__setor",
        local_field="item__local_estrutural",
    )
    return render(
        request,
        "almoxarifado/index.html",
        {
            "title": "Almoxarifado",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "cards": [
                {"label": "Itens ativos", "value": itens.filter(status=AlmoxarifadoCadastro.Status.ATIVO).count()},
                {"label": "Abaixo do mínimo", "value": sum(1 for i in itens if _to_dec(i.saldo_atual) < _to_dec(i.estoque_minimo))},
                {"label": "Requisições pendentes", "value": reqs.filter(status=AlmoxarifadoRequisicao.Status.PENDENTE).count()},
                {"label": "Movimentos hoje", "value": movs.filter(data_movimento=timezone.localdate()).count()},
                {"label": "Secretarias no escopo", "value": itens.exclude(secretaria_id=None).values("secretaria_id").distinct().count()},
                {"label": "Unidades no escopo", "value": itens.exclude(unidade_id=None).values("unidade_id").distinct().count()},
                {"label": "Locais no escopo", "value": itens.exclude(local_estrutural_id=None).values("local_estrutural_id").distinct().count()},
            ],
            "latest_reqs": reqs.select_related("item", "secretaria_solicitante", "unidade_solicitante", "local_solicitante").order_by("-criado_em")[:8],
            "latest_movs": movs.select_related("item", "item__secretaria", "item__unidade", "item__local_estrutural").order_by("-data_movimento", "-id")[:10],
            "actions": [
                {
                    "label": "Novo item",
                    "url": reverse("almoxarifado:item_create") + _q_municipio(municipio) + scope_qs,
                    "icon": "fa-solid fa-plus",
                    "variant": "gp-button--primary",
                },
                {
                    "label": "Requisições",
                    "url": reverse("almoxarifado:requisicao_list") + _q_municipio(municipio) + scope_qs,
                    "icon": "fa-solid fa-clipboard-list",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "Movimentos",
                    "url": reverse("almoxarifado:movimento_list") + _q_municipio(municipio) + scope_qs,
                    "icon": "fa-solid fa-right-left",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "Relatórios",
                    "url": reverse("almoxarifado:relatorios") + _q_municipio(municipio) + scope_qs,
                    "icon": "fa-solid fa-chart-column",
                    "variant": "gp-button--ghost",
                },
            ],
            **scope_ctx,
        },
    )

@login_required
@require_perm("almoxarifado.view")
def item_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    scope_ctx = _scope_context(request, municipio)
    scope_qs = _q_scope(request)
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    qs = _apply_scope_filters(
        request,
        AlmoxarifadoCadastro.objects.filter(municipio=municipio),
        secretaria_field="secretaria",
        unidade_field="unidade",
        setor_field="setor",
        local_field="local_estrutural",
    )
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(nome__icontains=q))
    if status:
        qs = qs.filter(status=status)

    export = (request.GET.get("export") or "").strip().lower()
    if export in {"csv", "pdf"}:
        rows = []
        for item in qs.order_by("nome"):
            rows.append(
                [
                    item.codigo,
                    item.nome,
                    item.unidade_medida,
                    item.get_status_display(),
                    str(item.saldo_atual),
                    str(item.estoque_minimo),
                    str(item.valor_medio),
                ]
            )
        headers = ["Codigo", "Nome", "Unidade", "Status", "Saldo", "Minimo", "Valor medio"]
        if export == "csv":
            return export_csv("almoxarifado_itens.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="almoxarifado_itens.pdf",
            title="Itens de estoque",
            subtitle=f"{municipio.nome}/{municipio.uf}",
            headers=headers,
            rows=rows,
            filtros=f"Busca={q or '-'} | Status={status or '-'}",
        )
    return render(
        request,
        "almoxarifado/item_list.html",
        {
            "title": "Itens de estoque",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("nome"),
            "q": q,
            "status": status,
            "status_choices": AlmoxarifadoCadastro.Status.choices,
            "actions": [
                {
                    "label": "Novo item",
                    "url": reverse("almoxarifado:item_create") + _q_municipio(municipio) + scope_qs,
                    "icon": "fa-solid fa-plus",
                    "variant": "gp-button--primary",
                },
                {
                    "label": "CSV",
                    "url": request.path + f"?municipio={municipio.pk}{scope_qs}&q={q}&status={status}&export=csv",
                    "icon": "fa-solid fa-file-csv",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "PDF",
                    "url": request.path + f"?municipio={municipio.pk}{scope_qs}&q={q}&status={status}&export=pdf",
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "Relatórios",
                    "url": reverse("almoxarifado:relatorios") + _q_municipio(municipio) + scope_qs,
                    "icon": "fa-solid fa-chart-column",
                    "variant": "gp-button--ghost",
                },
            ],
            **scope_ctx,
        },
    )

@login_required
@require_perm("almoxarifado.manage")
def item_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para criar item.")
        return redirect("almoxarifado:item_list")
    form = AlmoxarifadoCadastroForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        messages.success(request, "Item de estoque salvo.")
        return redirect(reverse("almoxarifado:item_list") + _q_municipio(municipio) + _q_scope(request))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo item de estoque",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("almoxarifado:item_list") + _q_municipio(municipio) + _q_scope(request),
            "submit_label": "Salvar item",
        },
    )

@login_required
@require_perm("almoxarifado.manage")
def item_update(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(AlmoxarifadoCadastro, pk=pk, municipio=municipio)
    form = AlmoxarifadoCadastroForm(request.POST or None, instance=obj, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Item atualizado.")
        return redirect(reverse("almoxarifado:item_list") + _q_municipio(municipio) + _q_scope(request))
    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Editar item {obj.codigo}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("almoxarifado:item_list") + _q_municipio(municipio) + _q_scope(request),
            "submit_label": "Salvar alterações",
        },
    )

@login_required
@require_perm("almoxarifado.view")
def movimento_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    scope_ctx = _scope_context(request, municipio)
    scope_qs = _q_scope(request)
    tipo = (request.GET.get("tipo") or "").strip()
    q = (request.GET.get("q") or "").strip()
    qs = _apply_scope_filters(
        request,
        AlmoxarifadoMovimento.objects.filter(municipio=municipio).select_related("item"),
        secretaria_field="item__secretaria",
        unidade_field="item__unidade",
        setor_field="item__setor",
        local_field="item__local_estrutural",
    )
    if tipo:
        qs = qs.filter(tipo=tipo)
    if q:
        qs = qs.filter(Q(item__codigo__icontains=q) | Q(item__nome__icontains=q))

    export = (request.GET.get("export") or "").strip().lower()
    if export in {"csv", "pdf"}:
        rows = []
        for item in qs.order_by("-data_movimento", "-id"):
            rows.append(
                [
                    str(item.data_movimento),
                    item.item.codigo,
                    item.item.nome,
                    item.get_tipo_display(),
                    str(item.quantidade),
                    str(item.valor_unitario),
                    item.documento or "",
                ]
            )
        headers = ["Data", "Item", "Descricao", "Tipo", "Quantidade", "Valor unitario", "Documento"]
        if export == "csv":
            return export_csv("almoxarifado_movimentos.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="almoxarifado_movimentos.pdf",
            title="Movimentos de estoque",
            subtitle=f"{municipio.nome}/{municipio.uf}",
            headers=headers,
            rows=rows,
            filtros=f"Busca={q or '-'} | Tipo={tipo or '-'}",
        )
    return render(
        request,
        "almoxarifado/movimento_list.html",
        {
            "title": "Movimentos de estoque",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-data_movimento", "-id"),
            "tipo": tipo,
            "q": q,
            "tipo_choices": AlmoxarifadoMovimento.Tipo.choices,
            "actions": [
                {
                    "label": "Novo movimento",
                    "url": reverse("almoxarifado:movimento_create") + _q_municipio(municipio) + scope_qs,
                    "icon": "fa-solid fa-plus",
                    "variant": "gp-button--primary",
                },
                {
                    "label": "CSV",
                    "url": request.path + f"?municipio={municipio.pk}{scope_qs}&q={q}&tipo={tipo}&export=csv",
                    "icon": "fa-solid fa-file-csv",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "PDF",
                    "url": request.path + f"?municipio={municipio.pk}{scope_qs}&q={q}&tipo={tipo}&export=pdf",
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "Relatórios",
                    "url": reverse("almoxarifado:relatorios") + _q_municipio(municipio) + scope_qs,
                    "icon": "fa-solid fa-chart-column",
                    "variant": "gp-button--ghost",
                },
            ],
            **scope_ctx,
        },
    )

@login_required
@require_perm("almoxarifado.manage")
def movimento_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para criar movimento.")
        return redirect("almoxarifado:movimento_list")
    form = AlmoxarifadoMovimentoForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        if obj.tipo == AlmoxarifadoMovimento.Tipo.SAIDA and _to_dec(obj.item.saldo_atual) < _to_dec(obj.quantidade):
            form.add_error("quantidade", "Saldo insuficiente para saída.")
        else:
            obj.save()
            _aplicar_movimento_estoque(obj)
            messages.success(request, "Movimento registrado.")
            return redirect(reverse("almoxarifado:movimento_list") + _q_municipio(municipio) + _q_scope(request))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo movimento de estoque",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("almoxarifado:movimento_list") + _q_municipio(municipio) + _q_scope(request),
            "submit_label": "Salvar movimento",
        },
    )


@login_required
@require_perm("almoxarifado.view")
def relatorios(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    scope_ctx = _scope_context(request, municipio)
    scope_qs = _q_scope(request)
    date_from_raw = (request.GET.get("data_inicio") or "").strip()
    date_to_raw = (request.GET.get("data_fim") or "").strip()
    date_from = _parse_date(date_from_raw)
    date_to = _parse_date(date_to_raw)

    itens_qs = _apply_scope_filters(
        request,
        AlmoxarifadoCadastro.objects.filter(municipio=municipio),
        secretaria_field="secretaria",
        unidade_field="unidade",
        setor_field="setor",
        local_field="local_estrutural",
    )
    movimentos_qs = _apply_scope_filters(
        request,
        AlmoxarifadoMovimento.objects.filter(municipio=municipio),
        secretaria_field="item__secretaria",
        unidade_field="item__unidade",
        setor_field="item__setor",
        local_field="item__local_estrutural",
    )
    requisicoes_qs = _apply_scope_filters(
        request,
        AlmoxarifadoRequisicao.objects.filter(municipio=municipio),
        secretaria_field="secretaria_solicitante",
        unidade_field="unidade_solicitante",
        setor_field="setor_solicitante",
        local_field="local_solicitante",
    )

    if date_from:
        movimentos_qs = movimentos_qs.filter(data_movimento__gte=date_from)
        requisicoes_qs = requisicoes_qs.filter(criado_em__date__gte=date_from)
    if date_to:
        movimentos_qs = movimentos_qs.filter(data_movimento__lte=date_to)
        requisicoes_qs = requisicoes_qs.filter(criado_em__date__lte=date_to)

    saldo_secretaria = list(
        itens_qs.values("secretaria__nome")
        .annotate(total_saldo=Coalesce(Sum("saldo_atual"), Value(0)), total_itens=Count("id"))
        .order_by("secretaria__nome")
    )
    saldo_unidade = list(
        itens_qs.values("unidade__nome")
        .annotate(total_saldo=Coalesce(Sum("saldo_atual"), Value(0)), total_itens=Count("id"))
        .order_by("unidade__nome")
    )
    saldo_local = list(
        itens_qs.annotate(local_nome=Coalesce("local_estrutural__nome", "setor__nome", Value("Sem local")))
        .values("local_nome")
        .annotate(total_saldo=Coalesce(Sum("saldo_atual"), Value(0)), total_itens=Count("id"))
        .order_by("local_nome")
    )
    consumo_periodo = list(
        movimentos_qs.filter(tipo=AlmoxarifadoMovimento.Tipo.SAIDA)
        .values("item__nome")
        .annotate(total_saida=Coalesce(Sum("quantidade"), Value(0)))
        .order_by("-total_saida", "item__nome")[:20]
    )
    req_por_secretaria = list(
        requisicoes_qs.values("secretaria_solicitante__nome")
        .annotate(
            pendentes=Count("id", filter=Q(status=AlmoxarifadoRequisicao.Status.PENDENTE)),
            atendidas=Count("id", filter=Q(status=AlmoxarifadoRequisicao.Status.ATENDIDA)),
            total=Count("id"),
        )
        .order_by("secretaria_solicitante__nome")
    )

    abaixo_minimo = itens_qs.filter(saldo_atual__lt=F("estoque_minimo")).count()
    transferencias = MovimentacaoEstoque.objects.filter(
        municipio=municipio,
        tipo_movimentacao=MovimentacaoEstoque.TipoMovimentacao.TRANSFERENCIA,
    ).count()

    export = (request.GET.get("export") or "").strip().lower()
    if export in {"csv", "pdf"}:
        headers = ["Tipo", "Agrupador", "Quantidade", "Valor"]
        rows: list[list[str]] = []
        for row in saldo_secretaria:
            rows.append(["Saldo por secretaria", row.get("secretaria__nome") or "Sem secretaria", str(row.get("total_itens") or 0), str(row.get("total_saldo") or 0)])
        for row in saldo_unidade:
            rows.append(["Saldo por unidade", row.get("unidade__nome") or "Sem unidade", str(row.get("total_itens") or 0), str(row.get("total_saldo") or 0)])
        for row in saldo_local:
            rows.append(["Saldo por local", row.get("local_nome") or "Sem local", str(row.get("total_itens") or 0), str(row.get("total_saldo") or 0)])
        for row in consumo_periodo:
            rows.append(["Consumo por período", row.get("item__nome") or "Sem item", str(row.get("total_saida") or 0), "0"])

        rows.append(["Indicador", "Produtos abaixo do mínimo", str(abaixo_minimo), "0"])
        rows.append(["Indicador", "Transferências registradas", str(transferencias), "0"])

        if export == "csv":
            return export_csv("almoxarifado_relatorios.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="almoxarifado_relatorios.pdf",
            title="Relatórios de almoxarifado",
            subtitle=f"{municipio.nome}/{municipio.uf}",
            headers=headers,
            rows=rows,
            filtros=f"Data início={date_from_raw or '-'} | Data fim={date_to_raw or '-'}",
        )

    return render(
        request,
        "almoxarifado/relatorios.html",
        {
            "title": "Relatórios de Almoxarifado",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "data_inicio": date_from_raw,
            "data_fim": date_to_raw,
            "saldo_secretaria": saldo_secretaria,
            "saldo_unidade": saldo_unidade,
            "saldo_local": saldo_local,
            "consumo_periodo": consumo_periodo,
            "req_por_secretaria": req_por_secretaria,
            "cards": [
                {"label": "Produtos abaixo do mínimo", "value": abaixo_minimo},
                {"label": "Transferências (novo modelo)", "value": transferencias},
                {"label": "Requisições pendentes", "value": requisicoes_qs.filter(status=AlmoxarifadoRequisicao.Status.PENDENTE).count()},
                {"label": "Requisições atendidas", "value": requisicoes_qs.filter(status=AlmoxarifadoRequisicao.Status.ATENDIDA).count()},
            ],
            "actions": [
                {"label": "Voltar ao painel", "url": reverse("almoxarifado:index") + _q_municipio(municipio) + scope_qs, "icon": "fa-solid fa-arrow-left", "variant": "gp-button--ghost"},
                {"label": "CSV", "url": request.path + f"?municipio={municipio.pk}{scope_qs}&data_inicio={date_from_raw}&data_fim={date_to_raw}&export=csv", "icon": "fa-solid fa-file-csv", "variant": "gp-button--ghost"},
                {"label": "PDF", "url": request.path + f"?municipio={municipio.pk}{scope_qs}&data_inicio={date_from_raw}&data_fim={date_to_raw}&export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "gp-button--ghost"},
            ],
            **scope_ctx,
        },
    )
