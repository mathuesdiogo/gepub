from __future__ import annotations

from .views_common import *
from .views_common import _municipios_admin, _resolve_municipio, _selected_exercicio

@login_required
@require_perm("financeiro.view")
def index(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        messages.error(request, "Selecione um município para acessar o financeiro.")
        return redirect("core:dashboard")

    exercicio = _selected_exercicio(request, municipio)

    dotacoes = OrcDotacao.objects.filter(municipio=municipio)
    empenhos = DespEmpenho.objects.filter(municipio=municipio)
    receitas = RecArrecadacao.objects.filter(municipio=municipio)

    if exercicio:
        dotacoes = dotacoes.filter(exercicio=exercicio)
        empenhos = empenhos.filter(exercicio=exercicio)
        receitas = receitas.filter(exercicio=exercicio)

    totais_dot = dotacoes.aggregate(
        valor_inicial=Sum("valor_inicial"),
        valor_atualizado=Sum("valor_atualizado"),
        valor_empenhado=Sum("valor_empenhado"),
        valor_liquidado=Sum("valor_liquidado"),
        valor_pago=Sum("valor_pago"),
    )
    total_receita = receitas.aggregate(valor=Sum("valor"))

    actions = [
        {
            "label": "Empenhar despesa",
            "url": reverse("financeiro:empenho_create") + f"?municipio={municipio.pk}",
            "icon": "fa-solid fa-file-signature",
            "variant": "btn-primary",
        },
        {
            "label": "Arrecadar receita",
            "url": reverse("financeiro:receita_create") + f"?municipio={municipio.pk}",
            "icon": "fa-solid fa-money-bill-trend-up",
            "variant": "btn--ghost",
        },
        {
            "label": "Dotações",
            "url": reverse("financeiro:dotacao_list") + f"?municipio={municipio.pk}",
            "icon": "fa-solid fa-chart-pie",
            "variant": "btn--ghost",
        },
        {
            "label": "Créditos adicionais",
            "url": reverse("financeiro:credito_list") + f"?municipio={municipio.pk}",
            "icon": "fa-solid fa-scale-balanced",
            "variant": "btn--ghost",
        },
        {
            "label": "Restos a pagar",
            "url": reverse("financeiro:resto_list") + f"?municipio={municipio.pk}",
            "icon": "fa-solid fa-receipt",
            "variant": "btn--ghost",
        },
    ]
    if can(request.user, "financeiro.tesouraria"):
        actions.append(
            {
                "label": "Conciliação bancária",
                "url": reverse("financeiro:extrato_list") + f"?municipio={municipio.pk}",
                "icon": "fa-solid fa-scale-balanced",
                "variant": "btn--ghost",
            }
        )

    kpis = [
        {"label": "Orçamento atualizado", "value": totais_dot["valor_atualizado"] or Decimal("0.00")},
        {"label": "Empenhado", "value": totais_dot["valor_empenhado"] or Decimal("0.00")},
        {"label": "Liquidado", "value": totais_dot["valor_liquidado"] or Decimal("0.00")},
        {"label": "Pago", "value": totais_dot["valor_pago"] or Decimal("0.00")},
        {"label": "Receita arrecadada", "value": total_receita["valor"] or Decimal("0.00")},
    ]

    return render(
        request,
        "financeiro/index.html",
        {
            "title": "Financeiro Público",
            "subtitle": f"{municipio.nome}/{municipio.uf} • visão operacional",
            "actions": actions,
            "kpis": kpis,
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "exercicio": exercicio,
            "exercicios": FinanceiroExercicio.objects.filter(municipio=municipio).order_by("-ano"),
            "empenhos_recentes": empenhos.select_related("unidade_gestora").order_by("-data_empenho", "-id")[:8],
            "receitas_recentes": receitas.order_by("-data_arrecadacao", "-id")[:8],
        },
    )

@login_required
@require_perm("financeiro.view")
def exercicio_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        messages.error(request, "Selecione um município para listar exercícios.")
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    qs = FinanceiroExercicio.objects.filter(municipio=municipio)
    if q:
        qs = qs.filter(Q(ano__icontains=q) | Q(status__icontains=q))

    return render(
        request,
        "financeiro/exercicio_list.html",
        {
            "title": "Exercícios",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-ano"),
            "q": q,
            "actions": [
                {
                    "label": "Novo exercício",
                    "url": reverse("financeiro:exercicio_create") + f"?municipio={municipio.pk}",
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
def exercicio_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para criar o exercício.")
        return redirect("financeiro:exercicio_list")

    form = FinanceiroExercicioForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.save()
        messages.success(request, "Exercício criado com sucesso.")
        return redirect(reverse("financeiro:exercicio_list") + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo exercício",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("financeiro:exercicio_list") + f"?municipio={municipio.pk}",
            "submit_label": "Salvar exercício",
        },
    )

@login_required
@require_perm("financeiro.manage")
def exercicio_update(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    obj = get_object_or_404(FinanceiroExercicio, pk=pk, municipio=municipio)
    form = FinanceiroExercicioForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Exercício atualizado com sucesso.")
        return redirect(reverse("financeiro:exercicio_list") + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Editar exercício",
            "subtitle": f"{obj.ano}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("financeiro:exercicio_list") + f"?municipio={municipio.pk}",
            "submit_label": "Atualizar exercício",
        },
    )

@login_required
@require_perm("financeiro.view")
def ug_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    qs = FinanceiroUnidadeGestora.objects.filter(municipio=municipio)
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(nome__icontains=q))

    return render(
        request,
        "financeiro/ug_list.html",
        {
            "title": "Unidades Gestoras",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("codigo", "nome"),
            "q": q,
            "actions": [
                {
                    "label": "Nova UG",
                    "url": reverse("financeiro:ug_create") + f"?municipio={municipio.pk}",
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
def ug_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para criar UG.")
        return redirect("financeiro:ug_list")

    form = FinanceiroUnidadeGestoraForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.save()
        messages.success(request, "Unidade gestora criada com sucesso.")
        return redirect(reverse("financeiro:ug_list") + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova Unidade Gestora",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("financeiro:ug_list") + f"?municipio={municipio.pk}",
            "submit_label": "Salvar UG",
        },
    )

@login_required
@require_perm("financeiro.view")
def conta_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    qs = FinanceiroContaBancaria.objects.filter(municipio=municipio).select_related("unidade_gestora")
    if q:
        qs = qs.filter(
            Q(banco_nome__icontains=q)
            | Q(agencia__icontains=q)
            | Q(conta__icontains=q)
            | Q(unidade_gestora__nome__icontains=q)
        )

    return render(
        request,
        "financeiro/conta_list.html",
        {
            "title": "Contas Bancárias",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("banco_nome", "agencia", "conta"),
            "q": q,
            "actions": [
                {
                    "label": "Nova conta",
                    "url": reverse("financeiro:conta_create") + f"?municipio={municipio.pk}",
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
def conta_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para criar conta bancária.")
        return redirect("financeiro:conta_list")

    form = FinanceiroContaBancariaForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.save()
        messages.success(request, "Conta bancária criada com sucesso.")
        return redirect(reverse("financeiro:conta_list") + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova conta bancária",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("financeiro:conta_list") + f"?municipio={municipio.pk}",
            "submit_label": "Salvar conta",
        },
    )

@login_required
@require_perm("financeiro.view")
def fonte_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    qs = OrcFonteRecurso.objects.filter(municipio=municipio)
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(nome__icontains=q))

    return render(
        request,
        "financeiro/fonte_list.html",
        {
            "title": "Fontes de Recurso",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("codigo", "nome"),
            "q": q,
            "actions": [
                {
                    "label": "Nova fonte",
                    "url": reverse("financeiro:fonte_create") + f"?municipio={municipio.pk}",
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
def fonte_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para criar fonte.")
        return redirect("financeiro:fonte_list")

    form = OrcFonteRecursoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.save()
        messages.success(request, "Fonte criada com sucesso.")
        return redirect(reverse("financeiro:fonte_list") + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova fonte de recurso",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("financeiro:fonte_list") + f"?municipio={municipio.pk}",
            "submit_label": "Salvar fonte",
        },
    )

@login_required
@require_perm("financeiro.view")
def dotacao_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    exercicio = _selected_exercicio(request, municipio)

    qs = OrcDotacao.objects.filter(municipio=municipio).select_related("exercicio", "unidade_gestora", "fonte")
    if exercicio:
        qs = qs.filter(exercicio=exercicio)
    if q:
        qs = qs.filter(
            Q(programa_codigo__icontains=q)
            | Q(programa_nome__icontains=q)
            | Q(acao_codigo__icontains=q)
            | Q(acao_nome__icontains=q)
            | Q(elemento_despesa__icontains=q)
        )

    return render(
        request,
        "financeiro/dotacao_list.html",
        {
            "title": "Dotações orçamentárias",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("programa_codigo", "acao_codigo"),
            "q": q,
            "exercicio": exercicio,
            "exercicios": FinanceiroExercicio.objects.filter(municipio=municipio).order_by("-ano"),
            "actions": [
                {
                    "label": "Nova dotação",
                    "url": reverse("financeiro:dotacao_create") + f"?municipio={municipio.pk}",
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
def dotacao_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para criar dotação.")
        return redirect("financeiro:dotacao_list")

    form = OrcDotacaoForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        if obj.valor_atualizado <= Decimal("0.00"):
            obj.valor_atualizado = obj.valor_inicial
        obj.save()
        messages.success(request, "Dotação criada com sucesso.")
        return redirect(reverse("financeiro:dotacao_list") + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova dotação",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("financeiro:dotacao_list") + f"?municipio={municipio.pk}",
            "submit_label": "Salvar dotação",
        },
    )

@login_required
@require_perm("financeiro.view")
def credito_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    exercicio = _selected_exercicio(request, municipio)

    qs = OrcCreditoAdicional.objects.filter(municipio=municipio).select_related("exercicio", "dotacao")
    if exercicio:
        qs = qs.filter(exercicio=exercicio)
    if q:
        qs = qs.filter(
            Q(numero_ato__icontains=q)
            | Q(origem_recurso__icontains=q)
            | Q(dotacao__programa_codigo__icontains=q)
            | Q(dotacao__acao_codigo__icontains=q)
        )

    return render(
        request,
        "financeiro/credito_list.html",
        {
            "title": "Créditos adicionais",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-data_ato", "-id"),
            "q": q,
            "exercicio": exercicio,
            "exercicios": FinanceiroExercicio.objects.filter(municipio=municipio).order_by("-ano"),
            "actions": [
                {
                    "label": "Novo crédito adicional",
                    "url": reverse("financeiro:credito_create") + f"?municipio={municipio.pk}",
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
def credito_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para registrar crédito adicional.")
        return redirect("financeiro:credito_list")

    form = OrcCreditoAdicionalForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user

        if obj.dotacao.municipio_id != municipio.id:
            messages.error(request, "A dotação selecionada não pertence ao município informado.")
        elif obj.dotacao.exercicio_id != obj.exercicio_id:
            messages.error(request, "A dotação selecionada precisa pertencer ao exercício informado.")
        else:
            obj.save()
            registrar_credito_adicional(obj, usuario=request.user)
            messages.success(request, "Crédito adicional registrado com sucesso.")
            return redirect(reverse("financeiro:credito_list") + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo crédito adicional",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("financeiro:credito_list") + f"?municipio={municipio.pk}",
            "submit_label": "Salvar crédito",
        },
    )
