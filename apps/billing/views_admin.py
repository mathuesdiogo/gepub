from __future__ import annotations

from decimal import Decimal

from .views_common import *
from .views_common import _metricas_para_tela
from apps.core.exports import export_csv


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

    export = (request.GET.get("export") or "").strip().lower()
    if export in {"csv", "pdf"}:
        headers = ["Municipio", "UF", "Plano", "Status", "Inicio", "Fim"]
        rows = []
        for item in qs.order_by("municipio__nome")[:5000]:
            rows.append(
                [
                    item.municipio.nome,
                    item.municipio.uf,
                    item.plano.nome,
                    item.get_status_display(),
                    str(item.inicio_vigencia),
                    str(item.fim_vigencia or ""),
                ]
            )
        if export == "csv":
            return export_csv("billing_assinaturas.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="billing_assinaturas.pdf",
            title="Assinaturas municipais",
            headers=headers,
            rows=rows,
            subtitle="Gestao central de municipios e planos",
            filtros=f"Busca={q or '-'} | Status={status or '-'}",
        )

    qs = qs.order_by("municipio__nome")
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page"))

    actions = [
        {
            "label": "Planos (Admin)",
            "url": reverse("billing:planos_admin"),
            "icon": "fa-solid fa-layer-group",
            "variant": "gp-button--ghost",
        },
        {
            "label": "Simulador",
            "url": reverse("billing:simulador"),
            "icon": "fa-solid fa-calculator",
            "variant": "gp-button--ghost",
        },
        {
            "label": "CSV",
            "url": reverse("billing:assinaturas_admin") + f"?q={q}&status={status}&export=csv",
            "icon": "fa-solid fa-file-csv",
            "variant": "gp-button--ghost",
        },
        {
            "label": "PDF",
            "url": reverse("billing:assinaturas_admin") + f"?q={q}&status={status}&export=pdf",
            "icon": "fa-solid fa-file-pdf",
            "variant": "gp-button--ghost",
        },
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
def planos_admin(request):
    q = (request.GET.get("q") or "").strip()
    planos_qs = PlanoMunicipal.objects.select_related("comercial_config").filter(
        codigo__in=[
            PlanoMunicipal.Codigo.STARTER,
            PlanoMunicipal.Codigo.MUNICIPAL,
            PlanoMunicipal.Codigo.GESTAO_TOTAL,
            PlanoMunicipal.Codigo.CONSORCIO,
        ]
    )
    if q:
        planos_qs = planos_qs.filter(Q(nome__icontains=q) | Q(codigo__icontains=q))

    planos = list(planos_qs.order_by("preco_base_mensal", "nome"))

    assinaturas_ativas = list(
        AssinaturaMunicipio.objects.select_related("plano").filter(
            plano__in=planos,
            status__in=[
                AssinaturaMunicipio.Status.ATIVO,
                AssinaturaMunicipio.Status.TRIAL,
                AssinaturaMunicipio.Status.SUSPENSO,
            ],
        )
    )

    por_plano_count: dict[int, int] = {}
    por_plano_receita: dict[int, Decimal] = {}
    for ass in assinaturas_ativas:
        pid = int(ass.plano_id)
        por_plano_count[pid] = por_plano_count.get(pid, 0) + 1
        por_plano_receita[pid] = por_plano_receita.get(pid, Decimal("0.00")) + ass.valor_base_mensal()

    planos_cards: list[dict] = []
    docs_pendentes = 0
    for plano in planos:
        comercial = plano_comercial_data(plano)
        has_docs = bool(comercial["links"].get("contratacao") and comercial["links"].get("servicos"))
        if not has_docs:
            docs_pendentes += 1
        planos_cards.append(
            {
                "plano": plano,
                "comercial": comercial,
                "assinaturas_ativas": por_plano_count.get(plano.pk, 0),
                "receita_mensal_estimada": por_plano_receita.get(plano.pk, Decimal("0.00")),
                "has_docs": has_docs,
            }
        )

    actions = [
        {
            "label": "Novo plano",
            "url": reverse("billing:plano_admin_create"),
            "icon": "fa-solid fa-plus",
            "variant": "gp-button--primary",
        },
        {
            "label": "Assinaturas",
            "url": reverse("billing:assinaturas_admin"),
            "icon": "fa-solid fa-building-shield",
            "variant": "gp-button--ghost",
        },
        {
            "label": "Simulador",
            "url": reverse("billing:simulador"),
            "icon": "fa-solid fa-calculator",
            "variant": "gp-button--ghost",
        },
    ]

    return render(
        request,
        "billing/planos_admin.html",
        {
            "title": "Planos (Admin)",
            "subtitle": "Catálogo comercial, limites, recursos e documentos contratuais",
            "actions": actions,
            "q": q,
            "planos_cards": planos_cards,
            "kpis": {
                "planos_total": len(planos_cards),
                "planos_ativos": sum(1 for c in planos_cards if c["plano"].ativo),
                "assinaturas_ativas": len(assinaturas_ativas),
                "receita_mensal_estimada": sum((c["receita_mensal_estimada"] for c in planos_cards), Decimal("0.00")),
                "docs_pendentes": docs_pendentes,
            },
        },
    )


@login_required
@require_perm("billing.admin")
def plano_admin_create(request):
    plano_form = PlanoMunicipalAdminForm(request.POST or None, prefix="plano")
    comercial_form = PlanoComercialConfigForm(request.POST or None, prefix="comercial")

    if request.method == "POST" and (request.POST.get("action") or "").strip() == "save":
        if plano_form.is_valid() and comercial_form.is_valid():
            plano = plano_form.save()
            config = comercial_form.save(commit=False)
            config.plano = plano
            config.save()
            messages.success(request, "Plano criado com sucesso.")
            return redirect("billing:plano_admin_detail", plano_id=plano.pk)
        messages.error(request, "Corrija os campos do plano para continuar.")

    return render(
        request,
        "billing/plano_admin_detail.html",
        {
            "title": "Novo plano",
            "subtitle": "Cadastro técnico e comercial do plano",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("billing:planos_admin"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                },
            ],
            "is_new": True,
            "plano_form": plano_form,
            "comercial_form": comercial_form,
            "plano_preview": None,
            "assinaturas_recentes": [],
            "modulos_destravados": [],
            "resumo_uso": {},
        },
    )


@login_required
@require_perm("billing.admin")
def plano_admin_detail(request, plano_id: int):
    plano = get_object_or_404(PlanoMunicipal.objects.select_related("comercial_config"), pk=plano_id)
    comercial_instance = getattr(plano, "comercial_config", None) or PlanoComercialConfig(plano=plano)
    preview_defaults = plano_comercial_data(plano)
    comercial_initial = None
    if not getattr(comercial_instance, "pk", None):
        comercial_initial = {
            "nome_comercial": preview_defaults.get("nome_comercial", ""),
            "categoria": preview_defaults.get("categoria", ""),
            "descricao_comercial": preview_defaults.get("descricao_comercial", ""),
            "link_documento_contratacao": (preview_defaults.get("links") or {}).get("contratacao", ""),
            "link_documento_servicos": (preview_defaults.get("links") or {}).get("servicos", ""),
            "beneficios_text": "\n".join(preview_defaults.get("beneficios", [])),
            "especiais_text": "\n".join(preview_defaults.get("especiais", [])),
            "limitacoes_text": "\n".join(preview_defaults.get("limitacoes", [])),
            "dependencias_text": "\n".join(preview_defaults.get("dependencias", [])),
        }

    plano_form = PlanoMunicipalAdminForm(request.POST or None, instance=plano, prefix="plano")
    comercial_form = PlanoComercialConfigForm(
        request.POST or None,
        initial=comercial_initial,
        instance=comercial_instance,
        prefix="comercial",
    )

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "save":
            if plano_form.is_valid() and comercial_form.is_valid():
                plano = plano_form.save()
                config = comercial_form.save(commit=False)
                config.plano = plano
                config.save()
                messages.success(request, "Plano atualizado.")
                return redirect("billing:plano_admin_detail", plano_id=plano.pk)
            messages.error(request, "Corrija os campos do plano para salvar.")
        elif action == "toggle_ativo":
            plano.ativo = not plano.ativo
            plano.save(update_fields=["ativo", "atualizado_em"])
            messages.success(request, "Status de ativação do plano atualizado.")
            return redirect("billing:plano_admin_detail", plano_id=plano.pk)

    assinaturas = AssinaturaMunicipio.objects.select_related("municipio").filter(plano=plano).order_by("-atualizado_em")
    assinaturas_recentes = list(assinaturas[:30])

    municipios_ativos = list(
        assinaturas.filter(
            status__in=[
                AssinaturaMunicipio.Status.ATIVO,
                AssinaturaMunicipio.Status.TRIAL,
                AssinaturaMunicipio.Status.SUSPENSO,
            ]
        )
        .values_list("municipio_id", flat=True)
        .distinct()
    )
    uso_qs = UsoMunicipio.objects.filter(municipio_id__in=municipios_ativos)
    resumo_uso = {
        "municipios": len(municipios_ativos),
        "secretarias": sum(int(item.secretarias_ativas or 0) for item in uso_qs),
        "usuarios": sum(int(item.usuarios_ativos or 0) for item in uso_qs),
        "alunos": sum(int(item.alunos_ativos or 0) for item in uso_qs),
        "atendimentos": sum(int(item.atendimentos_ano or 0) for item in uso_qs),
    }

    modulos_destravados = list(plano_comercial_data(plano).get("apps_habilitados", []))

    return render(
        request,
        "billing/plano_admin_detail.html",
        {
            "title": f"Plano • {plano.nome}",
            "subtitle": "Gestão completa de preço, limites, recursos e documentação comercial",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("billing:planos_admin"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "Assinaturas",
                    "url": reverse("billing:assinaturas_admin"),
                    "icon": "fa-solid fa-building-shield",
                    "variant": "gp-button--ghost",
                },
            ],
            "is_new": False,
            "plano": plano,
            "plano_form": plano_form,
            "comercial_form": comercial_form,
            "plano_preview": plano_comercial_data(plano),
            "assinaturas_recentes": assinaturas_recentes,
            "modulos_destravados": modulos_destravados,
            "resumo_uso": resumo_uso,
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
            "variant": "gp-button--ghost",
        },
        {
            "label": "Planos (Admin)",
            "url": reverse("billing:planos_admin"),
            "icon": "fa-solid fa-layer-group",
            "variant": "gp-button--ghost",
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
