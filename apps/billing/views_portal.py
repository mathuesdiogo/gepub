from __future__ import annotations

from .views_common import *
from .views_common import _metricas_para_tela, _resolve_municipio

@login_required
@require_perm("billing.view")
def index(request):
    if can(request.user, "billing.admin"):
        return redirect("billing:assinaturas_admin")
    return redirect("billing:meu_plano")

@login_required
@require_perm("billing.view")
def meu_plano(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        messages.error(request, "Defina um município para visualizar o plano.")
        return redirect("core:dashboard")

    assinatura = get_assinatura_ativa(municipio)
    if not assinatura:
        raise Http404("Município sem assinatura ativa e sem plano padrão configurado.")

    uso = recalc_uso_municipio(municipio)
    metricas = _metricas_para_tela(assinatura, uso)

    solicitacoes = SolicitacaoUpgrade.objects.filter(municipio=municipio).select_related(
        "solicitado_por", "aprovado_por", "addon", "plano_destino"
    )[:20]
    faturas = FaturaMunicipio.objects.filter(municipio=municipio)[:12]

    actions = [
        {
            "label": "Solicitar upgrade",
            "url": reverse("billing:solicitar_upgrade") + f"?municipio={municipio.pk}",
            "icon": "fa-solid fa-arrow-up-right-dots",
            "variant": "btn-primary",
        },
        {
            "label": "Simular novo plano",
            "url": reverse("billing:simulador"),
            "icon": "fa-solid fa-calculator",
            "variant": "btn--ghost",
        },
    ]

    if can(request.user, "billing.admin"):
        actions.insert(
            0,
            {
                "label": "Assinaturas",
                "url": reverse("billing:assinaturas_admin"),
                "icon": "fa-solid fa-building-shield",
                "variant": "btn--ghost",
            },
        )

    return render(
        request,
        "billing/meu_plano.html",
        {
            "title": "Meu Plano",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": actions,
            "municipio": municipio,
            "assinatura": assinatura,
            "uso": uso,
            "metricas": metricas,
            "solicitacoes": solicitacoes,
            "faturas": faturas,
            "municipios": Municipio.objects.order_by("nome") if is_admin(request.user) else [],
        },
    )

@login_required
@require_perm("billing.manage")
def solicitar_upgrade(request):
    municipio = _resolve_municipio(request, require_admin_select=True)
    if not municipio:
        messages.error(request, "Selecione um município para solicitar upgrade.")
        return redirect(reverse("billing:meu_plano"))

    assinatura = get_assinatura_ativa(municipio)
    if not assinatura:
        messages.error(request, "Município sem assinatura ativa.")
        return redirect(reverse("billing:meu_plano") + f"?municipio={municipio.pk}")

    initial = {}
    tipo_qs = (request.GET.get("tipo") or "").strip().upper()
    qtd_qs = (request.GET.get("qtd") or "").strip()
    if tipo_qs in {
        SolicitacaoUpgrade.Tipo.SECRETARIAS,
        SolicitacaoUpgrade.Tipo.USUARIOS,
        SolicitacaoUpgrade.Tipo.ALUNOS,
        SolicitacaoUpgrade.Tipo.ATENDIMENTOS,
        SolicitacaoUpgrade.Tipo.ADDON,
        SolicitacaoUpgrade.Tipo.TROCA_PLANO,
    }:
        initial["tipo"] = tipo_qs
    if qtd_qs.isdigit():
        initial["quantidade"] = int(qtd_qs)

    form = SolicitacaoUpgradeForm(
        request.POST or None,
        initial=initial,
        assinatura=assinatura,
    )

    preview_valor = None
    if request.method == "POST" and form.is_valid():
        solicitacao = form.save(commit=False)
        solicitacao.municipio = municipio
        solicitacao.assinatura = assinatura
        solicitacao.solicitado_por = request.user
        solicitacao.status = SolicitacaoUpgrade.Status.SOLICITADO
        solicitacao.valor_mensal_calculado = form.valor_calculado or solicitacao.valor_mensal_calculado
        solicitacao.save()
        messages.success(request, "Solicitação enviada para aprovação.")
        return redirect(reverse("billing:meu_plano") + f"?municipio={municipio.pk}")

    if form.is_bound and form.is_valid():
        preview_valor = form.valor_calculado

    actions = [
        {
            "label": "Voltar",
            "url": reverse("billing:meu_plano") + f"?municipio={municipio.pk}",
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }
    ]

    return render(
        request,
        "billing/solicitar_upgrade.html",
        {
            "title": "Solicitar upgrade",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": actions,
            "form": form,
            "preview_valor": preview_valor,
            "municipio": municipio,
            "assinatura": assinatura,
            "cancel_url": reverse("billing:meu_plano") + f"?municipio={municipio.pk}",
        },
    )

@login_required
@require_perm("billing.view")
def simulador(request):
    form = SimuladorPlanoForm(request.POST or None)
    resultado = None

    if request.method == "POST" and form.is_valid():
        resultado = simular_plano(
            secretarias=form.cleaned_data["numero_secretarias"],
            usuarios=form.cleaned_data["numero_usuarios"],
            alunos=form.cleaned_data["numero_alunos"],
            atendimentos=form.cleaned_data["atendimentos_estimados_ano"],
        )

        if resultado and request.POST.get("export") == "pdf":
            headers = ["Item", "Quantidade", "Valor unitário", "Valor total"]
            rows = [["Plano base", "1", f"R$ {resultado.preco_base}", f"R$ {resultado.preco_base}"]]
            for add in resultado.adicionais:
                rows.append(
                    [
                        add["nome"],
                        str(add["quantidade"]),
                        f"R$ {add['valor_unitario']}",
                        f"R$ {add['valor_total']}",
                    ]
                )
            rows.append(["Total adicional", "", "", f"R$ {resultado.total_adicionais}"])
            rows.append(["Total mensal", "", "", f"R$ {resultado.total_mensal}"])

            return export_pdf_table(
                request,
                filename="proposta_comercial_gepub.pdf",
                title=f"Proposta Comercial - {resultado.plano.nome}",
                headers=headers,
                rows=rows,
                subtitle=resultado.justificativa,
            )

    actions = [
        {
            "label": "Meu plano",
            "url": reverse("billing:meu_plano"),
            "icon": "fa-solid fa-file-contract",
            "variant": "btn--ghost",
        }
    ]
    return render(
        request,
        "billing/simulador.html",
        {
            "title": "Simulador de preço municipal",
            "subtitle": "Recomendação de plano para proposta e licitação",
            "actions": actions,
            "form": form,
            "resultado": resultado,
            "cancel_url": reverse("billing:index"),
        },
    )
