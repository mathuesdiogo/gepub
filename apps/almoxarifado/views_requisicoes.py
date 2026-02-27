from __future__ import annotations

from .views_common import *
from .views_common import _aplicar_movimento_estoque, _municipios_admin, _q_municipio, _resolve_municipio, _to_dec

@login_required
@require_perm("almoxarifado.view")
def requisicao_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    status = (request.GET.get("status") or "").strip()
    q = (request.GET.get("q") or "").strip()
    qs = AlmoxarifadoRequisicao.objects.filter(municipio=municipio).select_related("item", "secretaria_solicitante")
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(numero__icontains=q) | Q(item__nome__icontains=q))
    return render(
        request,
        "almoxarifado/requisicao_list.html",
        {
            "title": "Requisições de almoxarifado",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-criado_em"),
            "status": status,
            "q": q,
            "status_choices": AlmoxarifadoRequisicao.Status.choices,
            "actions": [
                {
                    "label": "Nova requisição",
                    "url": reverse("almoxarifado:requisicao_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            ],
        },
    )

@login_required
@require_perm("almoxarifado.manage")
def requisicao_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para criar requisição.")
        return redirect("almoxarifado:requisicao_list")
    form = AlmoxarifadoRequisicaoForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.status = AlmoxarifadoRequisicao.Status.PENDENTE
        obj.save()
        publicar_evento_transparencia(
            municipio=municipio,
            modulo="ALMOXARIFADO",
            tipo_evento="REQUISICAO_CRIADA",
            titulo=f"Requisição {obj.numero} registrada",
            referencia=obj.numero,
            dados={"item": obj.item.codigo, "quantidade": str(obj.quantidade)},
            publico=False,
        )
        messages.success(request, "Requisição criada.")
        return redirect(reverse("almoxarifado:requisicao_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova requisição de almoxarifado",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("almoxarifado:requisicao_list") + _q_municipio(municipio),
            "submit_label": "Salvar requisição",
        },
    )

@login_required
@require_perm("almoxarifado.manage")
@require_POST
def requisicao_aprovar(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(AlmoxarifadoRequisicao, pk=pk, municipio=municipio)
    if obj.status != AlmoxarifadoRequisicao.Status.PENDENTE:
        messages.warning(request, "Requisição não está pendente.")
        return redirect(reverse("almoxarifado:requisicao_list") + _q_municipio(municipio))
    obj.status = AlmoxarifadoRequisicao.Status.APROVADA
    obj.aprovado_por = request.user
    obj.aprovado_em = timezone.now()
    obj.save(update_fields=["status", "aprovado_por", "aprovado_em", "atualizado_em"])
    messages.success(request, "Requisição aprovada.")
    return redirect(reverse("almoxarifado:requisicao_list") + _q_municipio(municipio))

@login_required
@require_perm("almoxarifado.manage")
@require_POST
def requisicao_atender(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(AlmoxarifadoRequisicao, pk=pk, municipio=municipio)
    if obj.status not in {AlmoxarifadoRequisicao.Status.APROVADA, AlmoxarifadoRequisicao.Status.PENDENTE}:
        messages.warning(request, "Requisição não pode ser atendida no status atual.")
        return redirect(reverse("almoxarifado:requisicao_list") + _q_municipio(municipio))
    if _to_dec(obj.item.saldo_atual) < _to_dec(obj.quantidade):
        messages.error(request, "Saldo insuficiente para atender a requisição.")
        return redirect(reverse("almoxarifado:requisicao_list") + _q_municipio(municipio))

    mov = AlmoxarifadoMovimento.objects.create(
        municipio=municipio,
        item=obj.item,
        tipo=AlmoxarifadoMovimento.Tipo.SAIDA,
        data_movimento=timezone.localdate(),
        quantidade=obj.quantidade,
        valor_unitario=obj.item.valor_medio,
        documento=obj.numero,
        observacao=f"Atendimento da requisição {obj.numero}",
        criado_por=request.user,
    )
    _aplicar_movimento_estoque(mov)

    obj.status = AlmoxarifadoRequisicao.Status.ATENDIDA
    obj.atendido_por = request.user
    obj.atendido_em = timezone.now()
    obj.save(update_fields=["status", "atendido_por", "atendido_em", "atualizado_em"])

    registrar_auditoria(
        municipio=municipio,
        modulo="ALMOXARIFADO",
        evento="REQUISICAO_ATENDIDA",
        entidade="AlmoxarifadoRequisicao",
        entidade_id=obj.pk,
        usuario=request.user,
        depois={"numero": obj.numero, "item": obj.item.codigo, "quantidade": str(obj.quantidade)},
    )
    messages.success(request, "Requisição atendida e estoque atualizado.")
    return redirect(reverse("almoxarifado:requisicao_list") + _q_municipio(municipio))
