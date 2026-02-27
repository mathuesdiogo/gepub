from __future__ import annotations

from .views_common import *
from .views_common import _aplicar_movimento_estoque, _municipios_admin, _q_municipio, _resolve_municipio, _to_dec

@login_required
@require_perm("almoxarifado.view")
def index(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    itens = AlmoxarifadoCadastro.objects.filter(municipio=municipio)
    reqs = AlmoxarifadoRequisicao.objects.filter(municipio=municipio)
    movs = AlmoxarifadoMovimento.objects.filter(municipio=municipio)
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
            ],
            "latest_reqs": reqs.select_related("item").order_by("-criado_em")[:8],
            "latest_movs": movs.select_related("item").order_by("-data_movimento", "-id")[:10],
            "actions": [
                {
                    "label": "Novo item",
                    "url": reverse("almoxarifado:item_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Requisições",
                    "url": reverse("almoxarifado:requisicao_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-clipboard-list",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Movimentos",
                    "url": reverse("almoxarifado:movimento_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-right-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )

@login_required
@require_perm("almoxarifado.view")
def item_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    qs = AlmoxarifadoCadastro.objects.filter(municipio=municipio)
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(nome__icontains=q))
    if status:
        qs = qs.filter(status=status)
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
                    "url": reverse("almoxarifado:item_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            ],
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
        return redirect(reverse("almoxarifado:item_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo item de estoque",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("almoxarifado:item_list") + _q_municipio(municipio),
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
        return redirect(reverse("almoxarifado:item_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Editar item {obj.codigo}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("almoxarifado:item_list") + _q_municipio(municipio),
            "submit_label": "Salvar alterações",
        },
    )

@login_required
@require_perm("almoxarifado.view")
def movimento_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    tipo = (request.GET.get("tipo") or "").strip()
    q = (request.GET.get("q") or "").strip()
    qs = AlmoxarifadoMovimento.objects.filter(municipio=municipio).select_related("item")
    if tipo:
        qs = qs.filter(tipo=tipo)
    if q:
        qs = qs.filter(Q(item__codigo__icontains=q) | Q(item__nome__icontains=q))
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
                    "url": reverse("almoxarifado:movimento_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            ],
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
            return redirect(reverse("almoxarifado:movimento_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo movimento de estoque",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("almoxarifado:movimento_list") + _q_municipio(municipio),
            "submit_label": "Salvar movimento",
        },
    )
