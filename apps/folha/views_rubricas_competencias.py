from __future__ import annotations

from apps.core.exports import export_csv, export_pdf_table

from .views_common import *
from .views_common import _municipios_admin, _q_municipio, _recompute_competencia, _resolve_municipio

@login_required
@require_perm("folha.view")
def index(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    rubricas = FolhaCadastro.objects.filter(municipio=municipio)
    competencias = FolhaCompetencia.objects.filter(municipio=municipio)
    lancamentos = FolhaLancamento.objects.filter(municipio=municipio)

    return render(
        request,
        "folha/index.html",
        {
            "title": "Folha de Pagamento",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "cards": [
                {"label": "Rubricas ativas", "value": rubricas.filter(status=FolhaCadastro.Status.ATIVO).count()},
                {"label": "Competências abertas", "value": competencias.filter(status=FolhaCompetencia.Status.ABERTA).count()},
                {"label": "Lançamentos pendentes", "value": lancamentos.filter(status=FolhaLancamento.Status.PENDENTE).count()},
                {"label": "Integrações em aberto", "value": FolhaIntegracaoFinanceiro.objects.filter(municipio=municipio).exclude(status=FolhaIntegracaoFinanceiro.Status.CONCLUIDA).count()},
            ],
            "latest_competencias": competencias.order_by("-competencia")[:8],
            "latest_lancamentos": lancamentos.select_related("competencia", "evento", "servidor").order_by("-id")[:10],
            "actions": [
                {
                    "label": "Nova competência",
                    "url": reverse("folha:competencia_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-calendar-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Rubricas",
                    "url": reverse("folha:rubrica_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-list-check",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Lançamentos",
                    "url": reverse("folha:lancamento_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-file-invoice-dollar",
                    "variant": "btn--ghost",
                },
            ],
        },
    )

@login_required
@require_perm("folha.view")
def rubrica_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    q = (request.GET.get("q") or "").strip()
    tipo = (request.GET.get("tipo") or "").strip()
    status = (request.GET.get("status") or "").strip()

    qs = FolhaCadastro.objects.filter(municipio=municipio)
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(nome__icontains=q) | Q(formula_calculo__icontains=q))
    if tipo:
        qs = qs.filter(tipo_evento=tipo)
    if status:
        qs = qs.filter(status=status)

    export = (request.GET.get("export") or "").strip().lower()
    if export in {"csv", "pdf"}:
        rows = []
        for item in qs.order_by("codigo"):
            rows.append(
                [
                    item.codigo,
                    item.nome,
                    item.get_tipo_evento_display(),
                    item.get_status_display(),
                    str(item.valor_referencia),
                ]
            )
        headers = ["Codigo", "Nome", "Tipo", "Status", "Valor base"]
        if export == "csv":
            return export_csv("folha_rubricas.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="folha_rubricas.pdf",
            title="Rubricas de folha",
            subtitle=f"{municipio.nome}/{municipio.uf}",
            headers=headers,
            rows=rows,
            filtros=f"Busca={q or '-'} | Tipo={tipo or '-'} | Status={status or '-'}",
        )

    return render(
        request,
        "folha/rubrica_list.html",
        {
            "title": "Rubricas de folha",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("codigo"),
            "q": q,
            "tipo": tipo,
            "status": status,
            "tipo_choices": FolhaCadastro.TipoEvento.choices,
            "status_choices": FolhaCadastro.Status.choices,
            "actions": [
                {
                    "label": "Nova rubrica",
                    "url": reverse("folha:rubrica_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "CSV",
                    "url": request.path + f"?municipio={municipio.pk}&q={q}&tipo={tipo}&status={status}&export=csv",
                    "icon": "fa-solid fa-file-csv",
                    "variant": "btn--ghost",
                },
                {
                    "label": "PDF",
                    "url": request.path + f"?municipio={municipio.pk}&q={q}&tipo={tipo}&status={status}&export=pdf",
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Painel folha",
                    "url": reverse("folha:index") + _q_municipio(municipio),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )

@login_required
@require_perm("folha.manage")
def rubrica_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para criar rubrica.")
        return redirect("folha:rubrica_list")

    form = FolhaCadastroForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        registrar_auditoria(
            municipio=municipio,
            modulo="FOLHA",
            evento="RUBRICA_CRIADA",
            entidade="FolhaCadastro",
            entidade_id=obj.pk,
            usuario=request.user,
            depois={"codigo": obj.codigo, "nome": obj.nome, "tipo": obj.tipo_evento},
        )
        messages.success(request, "Rubrica salva com sucesso.")
        return redirect(reverse("folha:rubrica_list") + _q_municipio(municipio))

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova rubrica de folha",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("folha:rubrica_list") + _q_municipio(municipio),
            "submit_label": "Salvar rubrica",
        },
    )

@login_required
@require_perm("folha.manage")
def rubrica_update(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(FolhaCadastro, pk=pk, municipio=municipio)
    form = FolhaCadastroForm(request.POST or None, instance=obj, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Rubrica atualizada.")
        return redirect(reverse("folha:rubrica_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Editar rubrica {obj.codigo}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("folha:rubrica_list") + _q_municipio(municipio),
            "submit_label": "Salvar alterações",
        },
    )

@login_required
@require_perm("folha.view")
def competencia_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    status = (request.GET.get("status") or "").strip()
    qs = FolhaCompetencia.objects.filter(municipio=municipio)
    if status:
        qs = qs.filter(status=status)

    export = (request.GET.get("export") or "").strip().lower()
    if export in {"csv", "pdf"}:
        rows = []
        for item in qs.order_by("-competencia"):
            rows.append(
                [
                    item.competencia,
                    item.get_status_display(),
                    item.total_colaboradores,
                    str(item.total_proventos),
                    str(item.total_descontos),
                    str(item.total_liquido),
                ]
            )
        headers = ["Competencia", "Status", "Colaboradores", "Proventos", "Descontos", "Liquido"]
        if export == "csv":
            return export_csv("folha_competencias.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="folha_competencias.pdf",
            title="Competencias de folha",
            subtitle=f"{municipio.nome}/{municipio.uf}",
            headers=headers,
            rows=rows,
            filtros=f"Status={status or '-'}",
        )
    return render(
        request,
        "folha/competencia_list.html",
        {
            "title": "Competências de folha",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-competencia"),
            "status": status,
            "status_choices": FolhaCompetencia.Status.choices,
            "actions": [
                {
                    "label": "Nova competência",
                    "url": reverse("folha:competencia_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "CSV",
                    "url": request.path + f"?municipio={municipio.pk}&status={status}&export=csv",
                    "icon": "fa-solid fa-file-csv",
                    "variant": "btn--ghost",
                },
                {
                    "label": "PDF",
                    "url": request.path + f"?municipio={municipio.pk}&status={status}&export=pdf",
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Lançamentos",
                    "url": reverse("folha:lancamento_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-file-invoice-dollar",
                    "variant": "btn--ghost",
                },
            ],
        },
    )

@login_required
@require_perm("folha.manage")
def competencia_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para abrir competência.")
        return redirect("folha:competencia_list")
    form = FolhaCompetenciaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        try:
            obj.save()
        except IntegrityError:
            form.add_error("competencia", "Competência já cadastrada para o município.")
        else:
            messages.success(request, "Competência criada.")
            return redirect(reverse("folha:competencia_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova competência de folha",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("folha:competencia_list") + _q_municipio(municipio),
            "submit_label": "Salvar competência",
        },
    )

@login_required
@require_perm("folha.manage")
@require_POST
def competencia_processar(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(FolhaCompetencia, pk=pk, municipio=municipio)
    _recompute_competencia(obj)
    obj.status = FolhaCompetencia.Status.PROCESSADA
    obj.save(
        update_fields=[
            "status",
            "total_colaboradores",
            "total_proventos",
            "total_descontos",
            "total_liquido",
            "atualizado_em",
        ]
    )
    registrar_auditoria(
        municipio=municipio,
        modulo="FOLHA",
        evento="COMPETENCIA_PROCESSADA",
        entidade="FolhaCompetencia",
        entidade_id=obj.pk,
        usuario=request.user,
        depois={
            "competencia": obj.competencia,
            "total_colaboradores": obj.total_colaboradores,
            "total_liquido": str(obj.total_liquido),
        },
    )
    messages.success(request, "Competência processada com sucesso.")
    return redirect(reverse("folha:competencia_list") + _q_municipio(municipio))

@login_required
@require_perm("folha.manage")
@require_POST
def competencia_fechar(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(FolhaCompetencia, pk=pk, municipio=municipio)
    _recompute_competencia(obj)
    obj.status = FolhaCompetencia.Status.FECHADA
    obj.fechamento_em = timezone.now()
    obj.fechamento_por = request.user
    obj.save(
        update_fields=[
            "status",
            "fechamento_em",
            "fechamento_por",
            "total_colaboradores",
            "total_proventos",
            "total_descontos",
            "total_liquido",
            "atualizado_em",
        ]
    )
    publicar_evento_transparencia(
        municipio=municipio,
        modulo="FOLHA",
        tipo_evento="FOLHA_FECHADA",
        titulo=f"Folha da competência {obj.competencia} fechada",
        referencia=obj.competencia,
        valor=obj.total_liquido,
        dados={"colaboradores": obj.total_colaboradores},
        publico=False,
    )
    messages.success(request, "Competência fechada.")
    return redirect(reverse("folha:competencia_list") + _q_municipio(municipio))

@login_required
@require_perm("folha.manage")
@require_POST
def competencia_reabrir(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(FolhaCompetencia, pk=pk, municipio=municipio)
    obj.status = FolhaCompetencia.Status.ABERTA
    obj.fechamento_em = None
    obj.fechamento_por = None
    obj.save(update_fields=["status", "fechamento_em", "fechamento_por", "atualizado_em"])
    messages.success(request, "Competência reaberta.")
    return redirect(reverse("folha:competencia_list") + _q_municipio(municipio))
