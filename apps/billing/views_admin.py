from __future__ import annotations

from .views_common import *
from .views_common import _metricas_para_tela

@login_required
@require_perm("billing.admin")
def assinaturas_admin(request):
    filtro = FiltroAssinaturaForm(request.GET or None)
    qs = AssinaturaMunicipio.objects.select_related("municipio", "plano").all()

    q = ""
    status = ""
    if filtro.is_valid():
        q = (filtro.cleaned_data.get("q") or "").strip()
        status = (filtro.cleaned_data.get("status") or "").strip()

    if q:
        qs = qs.filter(
            Q(municipio__nome__icontains=q)
            | Q(plano__nome__icontains=q)
            | Q(municipio__uf__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)

    qs = qs.order_by("municipio__nome")
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page"))

    actions = [
        {
            "label": "Simulador",
            "url": reverse("billing:simulador"),
            "icon": "fa-solid fa-calculator",
            "variant": "btn--ghost",
        }
    ]

    return render(
        request,
        "billing/assinaturas_admin.html",
        {
            "title": "Assinaturas",
            "subtitle": "Gestão central de municípios e planos",
            "actions": actions,
            "filtro": filtro,
            "page_obj": page,
            "q": q,
            "status": status,
        },
    )

@login_required
@require_perm("billing.admin")
def assinatura_admin_detail(request, assinatura_id: int):
    assinatura = get_object_or_404(
        AssinaturaMunicipio.objects.select_related("municipio", "plano"),
        pk=assinatura_id,
    )

    assinatura_form = AssinaturaAdminForm(request.POST or None, instance=assinatura, prefix="assinatura")
    bonus_form = BonusQuotaForm(request.POST or None, prefix="bonus")

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "save_assinatura" and assinatura_form.is_valid():
            assinatura_form.save()
            messages.success(request, "Assinatura atualizada.")
            return redirect("billing:assinatura_admin_detail", assinatura_id=assinatura.pk)

        if action == "bonus_quota" and bonus_form.is_valid():
            validade_dias = bonus_form.cleaned_data.get("validade_dias")
            fim_vigencia = None
            if validade_dias:
                fim_vigencia = timezone.localdate() + timedelta(days=int(validade_dias))

            AssinaturaQuotaExtra.objects.create(
                assinatura=assinatura,
                tipo=bonus_form.cleaned_data["tipo"],
                quantidade=bonus_form.cleaned_data["quantidade"],
                origem=AssinaturaQuotaExtra.Origem.BONUS,
                descricao=bonus_form.cleaned_data.get("descricao") or "Bônus concedido no painel admin",
                fim_vigencia=fim_vigencia,
                criado_por=request.user,
            )
            messages.success(request, "Bônus de quota concedido.")
            return redirect("billing:assinatura_admin_detail", assinatura_id=assinatura.pk)

        if action == "approve_upgrade":
            sid = (request.POST.get("solicitacao_id") or "").strip()
            if sid.isdigit():
                solicitacao = get_object_or_404(SolicitacaoUpgrade, pk=int(sid), assinatura=assinatura)
                aprovar_upgrade(solicitacao, aprovado_por=request.user)
                messages.success(request, "Solicitação aprovada.")
                return redirect("billing:assinatura_admin_detail", assinatura_id=assinatura.pk)

        if action == "reject_upgrade":
            sid = (request.POST.get("solicitacao_id") or "").strip()
            if sid.isdigit():
                solicitacao = get_object_or_404(SolicitacaoUpgrade, pk=int(sid), assinatura=assinatura)
                recusar_upgrade(solicitacao, aprovado_por=request.user)
                messages.success(request, "Solicitação recusada.")
                return redirect("billing:assinatura_admin_detail", assinatura_id=assinatura.pk)

        if action == "gerar_fatura":
            fatura = gerar_fatura_mensal(assinatura)
            messages.success(request, f"Fatura de {fatura.competencia:%m/%Y} atualizada.")
            return redirect("billing:assinatura_admin_detail", assinatura_id=assinatura.pk)

    uso = recalc_uso_municipio(assinatura.municipio)
    metricas = _metricas_para_tela(assinatura, uso)

    solicitacoes = assinatura.solicitacoes_upgrade.select_related("solicitado_por", "aprovado_por", "addon", "plano_destino")[:25]
    faturas = assinatura.faturas.all()[:24]

    actions = [
        {
            "label": "Voltar",
            "url": reverse("billing:assinaturas_admin"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        },
    ]

    return render(
        request,
        "billing/assinatura_admin_detail.html",
        {
            "title": f"Assinatura • {assinatura.municipio.nome}/{assinatura.municipio.uf}",
            "subtitle": f"Plano atual: {assinatura.plano.nome}",
            "actions": actions,
            "assinatura": assinatura,
            "uso": uso,
            "metricas": metricas,
            "assinatura_form": assinatura_form,
            "bonus_form": bonus_form,
            "solicitacoes": solicitacoes,
            "faturas": faturas,
        },
    )

@login_required
@require_perm("billing.view")
def fatura_pdf(request, fatura_id: int):
    fatura = get_object_or_404(FaturaMunicipio.objects.select_related("municipio", "assinatura", "assinatura__plano"), pk=fatura_id)

    if not can(request.user, "billing.admin"):
        municipio = resolver_municipio_usuario(request.user)
        if not municipio or municipio.id != fatura.municipio_id:
            raise Http404

    headers = ["Descrição", "Valor"]
    rows = [
        ["Plano", fatura.assinatura.plano.nome],
        ["Competência", fatura.competencia.strftime("%m/%Y")],
        ["Valor base", f"R$ {fatura.valor_base}"],
        ["Desconto", f"R$ {fatura.valor_desconto}"],
        ["Adicionais", f"R$ {fatura.valor_adicionais}"],
        ["Total", f"R$ {fatura.valor_total}"],
        ["Status", fatura.get_status_display()],
    ]

    return export_pdf_table(
        request,
        filename=f"fatura_{fatura.municipio_id}_{fatura.competencia:%Y_%m}.pdf",
        title=f"Fatura GEPUB - {fatura.municipio.nome}/{fatura.municipio.uf}",
        headers=headers,
        rows=rows,
        subtitle="Licença SaaS municipal com implantação, suporte e manutenção.",
    )
