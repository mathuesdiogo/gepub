from __future__ import annotations

from .views_common import *
from .views_common import _municipios_admin, _q_municipio, _recompute_competencia, _resolve_municipio, _to_dec

@login_required
@require_perm("folha.view")
def lancamento_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    comp = (request.GET.get("competencia") or "").strip()
    status = (request.GET.get("status") or "").strip()
    q = (request.GET.get("q") or "").strip()
    qs = FolhaLancamento.objects.filter(municipio=municipio).select_related("competencia", "evento", "servidor")
    if comp:
        qs = qs.filter(competencia__competencia=comp)
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(servidor__first_name__icontains=q)
            | Q(servidor__last_name__icontains=q)
            | Q(servidor__username__icontains=q)
            | Q(evento__nome__icontains=q)
        )
    competencias = list(
        FolhaCompetencia.objects.filter(municipio=municipio).values_list("competencia", flat=True).order_by("-competencia")
    )
    return render(
        request,
        "folha/lancamento_list.html",
        {
            "title": "Lançamentos de folha",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-id"),
            "comp": comp,
            "status": status,
            "q": q,
            "competencias": competencias,
            "status_choices": FolhaLancamento.Status.choices,
            "actions": [
                {
                    "label": "Novo lançamento",
                    "url": reverse("folha:lancamento_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Competências",
                    "url": reverse("folha:competencia_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-calendar-days",
                    "variant": "btn--ghost",
                },
            ],
        },
    )

@login_required
@require_perm("folha.manage")
def lancamento_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para lançar folha.")
        return redirect("folha:lancamento_list")
    form = FolhaLancamentoForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.status = FolhaLancamento.Status.PENDENTE
        obj.save()
        comp = obj.competencia
        _recompute_competencia(comp)
        comp.save(update_fields=["total_colaboradores", "total_proventos", "total_descontos", "total_liquido", "atualizado_em"])
        messages.success(request, "Lançamento salvo com sucesso.")
        return redirect(reverse("folha:lancamento_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo lançamento de folha",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("folha:lancamento_list") + _q_municipio(municipio),
            "submit_label": "Salvar lançamento",
        },
    )

@login_required
@require_perm("folha.manage")
@require_POST
def enviar_financeiro(request, competencia_pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    comp = get_object_or_404(FolhaCompetencia, pk=competencia_pk, municipio=municipio)
    lancamentos = FolhaLancamento.objects.filter(competencia=comp, municipio=municipio)
    if not lancamentos.exists():
        messages.warning(request, "Não há lançamentos na competência para envio.")
        return redirect(reverse("folha:competencia_list") + _q_municipio(municipio))

    _recompute_competencia(comp)
    comp.save(update_fields=["total_colaboradores", "total_proventos", "total_descontos", "total_liquido", "atualizado_em"])

    integ, _ = FolhaIntegracaoFinanceiro.objects.get_or_create(
        municipio=municipio,
        competencia=comp,
        defaults={"status": FolhaIntegracaoFinanceiro.Status.PENDENTE},
    )
    integ.status = FolhaIntegracaoFinanceiro.Status.ENVIADA
    integ.total_enviado = comp.total_liquido
    integ.referencia_financeiro = f"FOLHA-{comp.competencia}"
    integ.enviado_em = timezone.now()
    integ.enviado_por = request.user
    integ.save(update_fields=["status", "total_enviado", "referencia_financeiro", "enviado_em", "enviado_por", "atualizado_em"])

    lancamentos.update(status=FolhaLancamento.Status.ENVIADO_FINANCEIRO, atualizado_em=timezone.now())
    publicar_evento_transparencia(
        municipio=municipio,
        modulo="FINANCEIRO",
        tipo_evento="FOLHA_ENVIADA_FINANCEIRO",
        titulo=f"Folha {comp.competencia} enviada ao financeiro",
        referencia=integ.referencia_financeiro,
        valor=integ.total_enviado,
        dados={"competencia": comp.competencia, "lancamentos": lancamentos.count()},
        publico=False,
    )
    registrar_auditoria(
        municipio=municipio,
        modulo="FOLHA",
        evento="FOLHA_ENVIADA_FINANCEIRO",
        entidade="FolhaIntegracaoFinanceiro",
        entidade_id=integ.pk,
        usuario=request.user,
        depois={"competencia": comp.competencia, "total_enviado": str(integ.total_enviado)},
    )
    messages.success(request, "Competência enviada para integração financeira.")
    return redirect(reverse("folha:competencia_list") + _q_municipio(municipio))

@login_required
@require_perm("folha.view")
def holerite_pdf(request, competencia_pk: int, servidor_id: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    comp = get_object_or_404(FolhaCompetencia, pk=competencia_pk, municipio=municipio)
    qs = FolhaLancamento.objects.filter(municipio=municipio, competencia=comp, servidor_id=servidor_id).select_related("evento", "servidor")
    if not qs.exists():
        messages.error(request, "Não há lançamentos para o holerite solicitado.")
        return redirect(reverse("folha:lancamento_list") + _q_municipio(municipio))

    servidor = qs.first().servidor
    rows = []
    total_proventos = Decimal("0")
    total_descontos = Decimal("0")
    for item in qs:
        valor = _to_dec(item.valor_calculado)
        if item.evento.tipo_evento == FolhaCadastro.TipoEvento.PROVENTO:
            total_proventos += valor
        else:
            total_descontos += valor
        rows.append(
            [
                item.evento.codigo,
                item.evento.nome,
                item.evento.get_tipo_evento_display(),
                str(item.quantidade),
                f"R$ {item.valor_calculado}",
            ]
        )
    rows.append(["", "TOTAL PROVENTOS", "", "", f"R$ {total_proventos}"])
    rows.append(["", "TOTAL DESCONTOS", "", "", f"R$ {total_descontos}"])
    rows.append(["", "LÍQUIDO", "", "", f"R$ {total_proventos - total_descontos}"])
    return export_pdf_table(
        request,
        filename=f"holerite_{comp.competencia}_{servidor.username}.pdf",
        title=f"Holerite {comp.competencia}",
        subtitle=servidor.get_full_name() or servidor.username,
        headers=["Código", "Rubrica", "Tipo", "Qtd.", "Valor"],
        rows=rows,
    )
