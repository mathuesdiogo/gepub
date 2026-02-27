from __future__ import annotations

from .views_common import *
from .views_common import _municipios_admin, _resolve_municipio

@login_required
@require_perm("financeiro.view")
def resto_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    exercicio = _selected_exercicio(request, municipio)

    qs = DespRestosPagar.objects.filter(municipio=municipio).select_related(
        "exercicio_origem",
        "exercicio_inscricao",
        "empenho",
    )
    if exercicio:
        qs = qs.filter(exercicio_inscricao=exercicio)
    if q:
        qs = qs.filter(
            Q(numero_inscricao__icontains=q)
            | Q(empenho__numero__icontains=q)
            | Q(empenho__fornecedor_nome__icontains=q)
        )

    return render(
        request,
        "financeiro/resto_list.html",
        {
            "title": "Restos a pagar",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-data_inscricao", "-id"),
            "q": q,
            "exercicio": exercicio,
            "exercicios": FinanceiroExercicio.objects.filter(municipio=municipio).order_by("-ano"),
            "actions": [
                {
                    "label": "Inscrever resto a pagar",
                    "url": reverse("financeiro:resto_create") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-plus",
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
@require_perm("financeiro.manage")
def resto_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para inscrever restos a pagar.")
        return redirect("financeiro:resto_list")

    initial = {}
    empenho_id = (request.GET.get("empenho") or "").strip()
    if empenho_id.isdigit():
        initial["empenho"] = int(empenho_id)

    form = DespRestosPagarForm(request.POST or None, municipio=municipio, initial=initial)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.exercicio_origem = obj.empenho.exercicio

        if obj.empenho.municipio_id != municipio.id:
            messages.error(request, "O empenho selecionado não pertence ao município informado.")
        elif obj.valor_inscrito > obj.empenho.saldo_a_pagar:
            messages.error(request, "Valor inscrito excede o saldo a pagar do empenho.")
        else:
            obj.save()
            registrar_resto_pagar(obj, usuario=request.user)
            messages.success(request, "Resto a pagar inscrito com sucesso.")
            return redirect(reverse("financeiro:resto_detail", args=[obj.pk]) + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Inscrição em restos a pagar",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("financeiro:resto_list") + f"?municipio={municipio.pk}",
            "submit_label": "Salvar inscrição",
        },
    )

@login_required
@require_perm("financeiro.view")
def resto_detail(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    resto = get_object_or_404(
        DespRestosPagar.objects.select_related("exercicio_origem", "exercicio_inscricao", "empenho"),
        pk=pk,
        municipio=municipio,
    )

    pagamentos = list(resto.pagamentos.select_related("conta_bancaria").order_by("-data_pagamento", "-id"))

    actions = [
        {
            "label": "Voltar",
            "url": reverse("financeiro:resto_list") + f"?municipio={municipio.pk}",
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }
    ]
    if resto.saldo_a_pagar > Decimal("0.00"):
        actions.append(
            {
                "label": "Registrar pagamento",
                "url": reverse("financeiro:resto_pagamento_create", args=[resto.pk]) + f"?municipio={municipio.pk}",
                "icon": "fa-solid fa-money-check-dollar",
                "variant": "btn-primary",
            }
        )

    fields = [
        {"label": "Número inscrição", "value": resto.numero_inscricao},
        {"label": "Data inscrição", "value": resto.data_inscricao},
        {"label": "Empenho origem", "value": resto.empenho.numero},
        {"label": "Fornecedor", "value": resto.empenho.fornecedor_nome},
        {"label": "Tipo", "value": resto.get_tipo_display()},
        {"label": "Status", "value": resto.get_status_display()},
        {"label": "Exercício origem", "value": resto.exercicio_origem.ano},
        {"label": "Exercício inscrição", "value": resto.exercicio_inscricao.ano},
    ]

    pills = [
        {"label": "Valor inscrito", "value": resto.valor_inscrito},
        {"label": "Valor pago", "value": resto.valor_pago},
        {"label": "Saldo a pagar", "value": resto.saldo_a_pagar},
    ]

    return render(
        request,
        "financeiro/resto_detail.html",
        {
            "title": f"Resto a pagar {resto.numero_inscricao}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": actions,
            "obj": resto,
            "fields": fields,
            "pills": pills,
            "pagamentos": pagamentos,
            "municipio": municipio,
        },
    )

@login_required
@require_perm("financeiro.manage")
def resto_pagamento_create(request, resto_pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    resto = get_object_or_404(DespRestosPagar.objects.select_related("empenho"), pk=resto_pk, municipio=municipio)
    saldo_a_pagar = resto.saldo_a_pagar
    form = DespPagamentoRestoForm(request.POST or None, municipio=municipio)

    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.resto = resto
        obj.criado_por = request.user

        if obj.valor > saldo_a_pagar:
            messages.error(request, "Valor do pagamento excede o saldo a pagar do resto.")
        else:
            obj.save()
            try:
                registrar_pagamento_resto(obj, usuario=request.user)
            except ValueError as exc:
                messages.error(request, str(exc))
                obj.delete()
            else:
                messages.success(request, "Pagamento de resto a pagar registrado com sucesso.")
                return redirect(reverse("financeiro:resto_detail", args=[resto.pk]) + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Pagamento de RP • {resto.numero_inscricao}",
            "subtitle": f"Saldo a pagar: {saldo_a_pagar}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("financeiro:resto_detail", args=[resto.pk]) + f"?municipio={municipio.pk}",
            "submit_label": "Registrar pagamento",
        },
    )

@login_required
@require_perm("financeiro.view")
def empenho_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    exercicio = _selected_exercicio(request, municipio)

    qs = DespEmpenho.objects.filter(municipio=municipio).select_related("exercicio", "unidade_gestora", "dotacao")
    if exercicio:
        qs = qs.filter(exercicio=exercicio)
    if q:
        qs = qs.filter(
            Q(numero__icontains=q)
            | Q(fornecedor_nome__icontains=q)
            | Q(fornecedor_documento__icontains=q)
            | Q(objeto__icontains=q)
        )

    return render(
        request,
        "financeiro/empenho_list.html",
        {
            "title": "Empenhos",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-data_empenho", "-id"),
            "q": q,
            "exercicio": exercicio,
            "exercicios": FinanceiroExercicio.objects.filter(municipio=municipio).order_by("-ano"),
            "actions": [
                {
                    "label": "Novo empenho",
                    "url": reverse("financeiro:empenho_create") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-plus",
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
@require_perm("financeiro.manage")
def empenho_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para criar empenho.")
        return redirect("financeiro:empenho_list")

    form = DespEmpenhoForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user

        if obj.dotacao.municipio_id != municipio.id:
            messages.error(request, "A dotação selecionada não pertence ao município informado.")
        elif obj.valor_empenhado > obj.dotacao.saldo_disponivel:
            messages.error(request, "Valor do empenho excede o saldo disponível da dotação.")
        else:
            obj.save()
            registrar_empenho(obj, usuario=request.user)
            messages.success(request, "Empenho registrado com sucesso.")
            return redirect(reverse("financeiro:empenho_detail", args=[obj.pk]) + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo empenho",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("financeiro:empenho_list") + f"?municipio={municipio.pk}",
            "submit_label": "Salvar empenho",
        },
    )

@login_required
@require_perm("financeiro.view")
def empenho_detail(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    empenho = get_object_or_404(
        DespEmpenho.objects.select_related("dotacao", "exercicio", "unidade_gestora"),
        pk=pk,
        municipio=municipio,
    )

    liquidacoes = list(empenho.liquidacoes.order_by("-data_liquidacao", "-id"))
    pagamentos = list(DespPagamento.objects.filter(liquidacao__empenho=empenho).select_related("liquidacao").order_by("-data_pagamento", "-id"))

    actions = [
        {
            "label": "Voltar",
            "url": reverse("financeiro:empenho_list") + f"?municipio={municipio.pk}",
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }
    ]
    if request.user and request.user.is_authenticated:
        actions.append(
            {
                "label": "Registrar liquidação",
                "url": reverse("financeiro:liquidacao_create", args=[empenho.pk]) + f"?municipio={municipio.pk}",
                "icon": "fa-solid fa-clipboard-check",
                "variant": "btn-primary",
            }
        )
        if empenho.saldo_a_pagar > Decimal("0.00"):
            actions.append(
                {
                    "label": "Inscrever em RP",
                    "url": reverse("financeiro:resto_create") + f"?municipio={municipio.pk}&empenho={empenho.pk}",
                    "icon": "fa-solid fa-receipt",
                    "variant": "btn--ghost",
                }
            )

    fields = [
        {"label": "Número", "value": empenho.numero},
        {"label": "Data", "value": empenho.data_empenho},
        {"label": "Fornecedor", "value": empenho.fornecedor_nome},
        {"label": "Documento", "value": empenho.fornecedor_documento or "—"},
        {"label": "Tipo", "value": empenho.get_tipo_display()},
        {"label": "Status", "value": empenho.get_status_display()},
        {"label": "Objeto", "value": empenho.objeto or "—"},
    ]

    pills = [
        {"label": "Valor empenhado", "value": empenho.valor_empenhado},
        {"label": "Valor liquidado", "value": empenho.valor_liquidado},
        {"label": "Valor pago", "value": empenho.valor_pago},
        {"label": "Saldo a liquidar", "value": empenho.saldo_a_liquidar},
        {"label": "Saldo a pagar", "value": empenho.saldo_a_pagar},
    ]

    return render(
        request,
        "financeiro/empenho_detail.html",
        {
            "title": f"Empenho {empenho.numero}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": actions,
            "obj": empenho,
            "fields": fields,
            "pills": pills,
            "liquidacoes": liquidacoes,
            "pagamentos": pagamentos,
            "municipio": municipio,
        },
    )

@login_required
@require_perm("financeiro.manage")
def liquidacao_create(request, empenho_pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    empenho = get_object_or_404(DespEmpenho, pk=empenho_pk, municipio=municipio)
    form = DespLiquidacaoForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.empenho = empenho
        obj.criado_por = request.user

        if obj.valor_liquidado > empenho.saldo_a_liquidar:
            messages.error(request, "Valor da liquidação excede o saldo a liquidar do empenho.")
        else:
            obj.save()
            registrar_liquidacao(obj, usuario=request.user)
            messages.success(request, "Liquidação registrada com sucesso.")
            return redirect(reverse("financeiro:empenho_detail", args=[empenho.pk]) + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Liquidação • Empenho {empenho.numero}",
            "subtitle": f"Saldo a liquidar: {empenho.saldo_a_liquidar}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("financeiro:empenho_detail", args=[empenho.pk]) + f"?municipio={municipio.pk}",
            "submit_label": "Registrar liquidação",
        },
    )

@login_required
@require_perm("financeiro.manage")
def pagamento_create(request, liquidacao_pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    liquidacao = get_object_or_404(DespLiquidacao.objects.select_related("empenho"), pk=liquidacao_pk)
    if liquidacao.empenho.municipio_id != municipio.id:
        raise Http404

    saldo_a_pagar = liquidacao.empenho.saldo_a_pagar
    form = DespPagamentoForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.liquidacao = liquidacao
        obj.criado_por = request.user

        if obj.valor_pago > saldo_a_pagar:
            messages.error(request, "Valor do pagamento excede o saldo a pagar do empenho.")
        else:
            obj.save()
            registrar_pagamento(obj, usuario=request.user)
            messages.success(request, "Pagamento registrado com sucesso.")
            return redirect(reverse("financeiro:empenho_detail", args=[liquidacao.empenho.pk]) + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Pagamento • Liquidação {liquidacao.numero}",
            "subtitle": f"Saldo a pagar no empenho: {saldo_a_pagar}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("financeiro:empenho_detail", args=[liquidacao.empenho.pk]) + f"?municipio={municipio.pk}",
            "submit_label": "Registrar pagamento",
        },
    )

@login_required
@require_perm("financeiro.view")
def receita_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    exercicio = _selected_exercicio(request, municipio)

    qs = RecArrecadacao.objects.filter(municipio=municipio).select_related("exercicio", "unidade_gestora", "conta_bancaria")
    if exercicio:
        qs = qs.filter(exercicio=exercicio)
    if q:
        qs = qs.filter(Q(rubrica_codigo__icontains=q) | Q(rubrica_nome__icontains=q) | Q(origem__icontains=q))

    return render(
        request,
        "financeiro/receita_list.html",
        {
            "title": "Receitas arrecadadas",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-data_arrecadacao", "-id"),
            "q": q,
            "exercicio": exercicio,
            "exercicios": FinanceiroExercicio.objects.filter(municipio=municipio).order_by("-ano"),
            "actions": [
                {
                    "label": "Nova arrecadação",
                    "url": reverse("financeiro:receita_create") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-plus",
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
@require_perm("financeiro.manage")
def receita_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para registrar receita.")
        return redirect("financeiro:receita_list")

    form = RecArrecadacaoForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        registrar_arrecadacao(obj, usuario=request.user)
        messages.success(request, "Arrecadação registrada com sucesso.")
        return redirect(reverse("financeiro:receita_list") + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova arrecadação",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("financeiro:receita_list") + f"?municipio={municipio.pk}",
            "submit_label": "Salvar arrecadação",
        },
    )

@login_required
@require_perm("financeiro.view")
def log_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    qs = FinanceiroLogEvento.objects.filter(municipio=municipio).select_related("usuario")
    if q:
        qs = qs.filter(Q(evento__icontains=q) | Q(entidade__icontains=q) | Q(observacao__icontains=q))

    return render(
        request,
        "financeiro/log_list.html",
        {
            "title": "Logs e auditoria",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-criado_em", "-id")[:500],
            "q": q,
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("financeiro:index") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )
