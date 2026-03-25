from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import require_perm
from apps.core.exports import export_csv, export_pdf_table
from apps.core.rbac import can
from apps.core.services_auditoria import registrar_auditoria

from .forms import (
    RhPdpNecessidadeForm,
    RhPdpPlanoForm,
    RhRemanejamentoEditalForm,
    RhRemanejamentoInscricaoForm,
    RhRemanejamentoRecursoForm,
    RhSubstituicaoServidorForm,
)
from .models import (
    RhPdpNecessidade,
    RhPdpPlano,
    RhRemanejamentoEdital,
    RhRemanejamentoInscricao,
    RhRemanejamentoRecurso,
    RhSubstituicaoServidor,
)
from .views import _municipios_admin, _q_municipio, _resolve_municipio


def _is_manager(user) -> bool:
    return can(user, "rh.manage")


def _is_owner_inscricao(user, inscricao: RhRemanejamentoInscricao) -> bool:
    return bool(inscricao.servidor_id and inscricao.servidor.servidor_id and inscricao.servidor.servidor_id == user.id)


def _sync_substituicoes_status(municipio):
    for item in RhSubstituicaoServidor.objects.filter(municipio=municipio).only(
        "id", "status", "data_inicio", "data_fim", "atualizado_em"
    ):
        item.sync_status()


@login_required
@require_perm("rh.view")
def remanejamento_edital_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    status = (request.GET.get("status") or "").strip()
    tipo = (request.GET.get("tipo") or "").strip()
    q = (request.GET.get("q") or "").strip()

    qs = RhRemanejamentoEdital.objects.filter(municipio=municipio)
    if status:
        qs = qs.filter(status=status)
    if tipo:
        qs = qs.filter(tipo_servidor=tipo)
    if q:
        qs = qs.filter(Q(numero__icontains=q) | Q(titulo__icontains=q))

    export = (request.GET.get("export") or "").strip().lower()
    if export in {"csv", "pdf"}:
        rows = []
        for item in qs.order_by("-inscricao_inicio", "-id"):
            rows.append(
                [
                    item.numero,
                    item.titulo,
                    item.get_tipo_servidor_display(),
                    str(item.inscricao_inicio),
                    str(item.inscricao_fim),
                    item.get_status_display(),
                    str(item.inscricoes.filter(status=RhRemanejamentoInscricao.Status.VALIDA).count()),
                ]
            )
        headers = ["Numero", "Titulo", "Tipo", "Inicio", "Fim", "Status", "Inscricoes validas"]
        if export == "csv":
            return export_csv("rh_remanejamento_editais.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="rh_remanejamento_editais.pdf",
            title="Editais de remanejamento",
            subtitle=f"{municipio.nome}/{municipio.uf}",
            headers=headers,
            rows=rows,
            filtros=f"Busca={q or '-'} | Tipo={tipo or '-'} | Status={status or '-'}",
        )

    return render(
        request,
        "rh/remanejamento_edital_list.html",
        {
            "title": "Remanejamento",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-inscricao_inicio", "-id"),
            "status": status,
            "tipo": tipo,
            "q": q,
            "status_choices": RhRemanejamentoEdital.Status.choices,
            "tipo_choices": RhRemanejamentoEdital.TipoServidor.choices,
            "actions": [
                *(
                    [
                        {
                            "label": "Novo edital",
                            "url": reverse("rh:remanejamento_edital_create") + _q_municipio(municipio),
                            "icon": "fa-solid fa-plus",
                            "variant": "gp-button--primary",
                        }
                    ]
                    if _is_manager(request.user)
                    else []
                ),
                {
                    "label": "CSV",
                    "url": request.path + f"?municipio={municipio.pk}&q={q}&tipo={tipo}&status={status}&export=csv",
                    "icon": "fa-solid fa-file-csv",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "PDF",
                    "url": request.path + f"?municipio={municipio.pk}&q={q}&tipo={tipo}&status={status}&export=pdf",
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "Painel RH",
                    "url": reverse("rh:index") + _q_municipio(municipio),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("rh.manage")
def remanejamento_edital_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para adicionar edital.")
        return redirect("rh:remanejamento_edital_list")

    form = RhRemanejamentoEditalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        registrar_auditoria(
            municipio=municipio,
            modulo="RH",
            evento="REMANEJAMENTO_EDITAL_CRIADO",
            entidade="RhRemanejamentoEdital",
            entidade_id=obj.pk,
            usuario=request.user,
            depois={"numero": obj.numero, "status": obj.status},
        )
        messages.success(request, "Edital de remanejamento criado.")
        return redirect(reverse("rh:remanejamento_edital_detail", args=[obj.pk]) + _q_municipio(municipio))

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo edital de remanejamento",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "form": form,
            "cancel_url": reverse("rh:remanejamento_edital_list") + _q_municipio(municipio),
            "submit_label": "Salvar edital",
        },
    )


@login_required
@require_perm("rh.view")
def remanejamento_edital_detail(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    edital = get_object_or_404(RhRemanejamentoEdital, pk=pk, municipio=municipio)
    is_manager = _is_manager(request.user)

    if request.method == "POST" and is_manager:
        action = (request.POST.get("_action") or "").strip()
        if action in {RhRemanejamentoEdital.Status.RASCUNHO, RhRemanejamentoEdital.Status.ABERTO, RhRemanejamentoEdital.Status.ENCERRADO, RhRemanejamentoEdital.Status.ARQUIVADO}:
            before = edital.status
            edital.status = action
            edital.save(update_fields=["status", "atualizado_em"])
            registrar_auditoria(
                municipio=municipio,
                modulo="RH",
                evento="REMANEJAMENTO_EDITAL_STATUS",
                entidade="RhRemanejamentoEdital",
                entidade_id=edital.pk,
                usuario=request.user,
                antes={"status": before},
                depois={"status": edital.status},
            )
            messages.success(request, "Status do edital atualizado.")
            return redirect(reverse("rh:remanejamento_edital_detail", args=[edital.pk]) + _q_municipio(municipio))

    inscricoes = (
        RhRemanejamentoInscricao.objects.filter(edital=edital)
        .select_related("servidor", "criado_por")
        .prefetch_related("unidades_interesse")
        .order_by("-criado_em", "-id")
    )
    recursos = (
        RhRemanejamentoRecurso.objects.filter(inscricao__edital=edital)
        .select_related("inscricao", "inscricao__servidor", "respondido_por")
        .order_by("-criado_em", "-id")
    )

    return render(
        request,
        "rh/remanejamento_edital_detail.html",
        {
            "title": f"Edital {edital.numero}",
            "subtitle": edital.titulo,
            "municipio": municipio,
            "edital": edital,
            "is_manager": is_manager,
            "inscricoes": inscricoes,
            "recursos": recursos,
            "cards": [
                {"label": "Inscrições válidas", "value": inscricoes.filter(status=RhRemanejamentoInscricao.Status.VALIDA).count()},
                {"label": "Inscrições canceladas", "value": inscricoes.filter(status=RhRemanejamentoInscricao.Status.CANCELADA).count()},
                {"label": "Recursos pendentes", "value": recursos.filter(status=RhRemanejamentoRecurso.Status.PENDENTE).count()},
                {"label": "Status do edital", "value": edital.get_status_display()},
            ],
            "actions": [
                {
                    "label": "Nova inscrição",
                    "url": reverse("rh:remanejamento_inscricao_create", args=[edital.pk]) + _q_municipio(municipio),
                    "icon": "fa-solid fa-file-signature",
                    "variant": "gp-button--primary",
                },
                {
                    "label": "Voltar",
                    "url": reverse("rh:remanejamento_edital_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("rh.view")
def remanejamento_inscricao_create(request, edital_pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    edital = get_object_or_404(RhRemanejamentoEdital, pk=edital_pk, municipio=municipio)
    is_manager = _is_manager(request.user)
    if not is_manager and not edital.inscricao_aberta:
        return HttpResponseForbidden("403 — O período de inscrição deste edital não está aberto.")

    form = RhRemanejamentoInscricaoForm(
        request.POST or None,
        request.FILES or None,
        municipio=municipio,
        user=request.user,
        is_manager=is_manager,
    )
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.edital = edital
        obj.criado_por = request.user
        obj.status = RhRemanejamentoInscricao.Status.VALIDA
        if not is_manager and obj.servidor.servidor_id != request.user.id:
            return HttpResponseForbidden("403 — Você só pode realizar sua própria inscrição.")

        previous = RhRemanejamentoInscricao.objects.filter(
            edital=edital,
            servidor=obj.servidor,
            status=RhRemanejamentoInscricao.Status.VALIDA,
        ).first()
        if previous:
            previous.status = RhRemanejamentoInscricao.Status.CANCELADA
            previous.motivo_cancelamento = "Substituída por nova inscrição."
            previous.save(update_fields=["status", "motivo_cancelamento", "atualizado_em"])

        obj.save()
        form.save_m2m()
        if not obj.protocolo:
            obj.protocolo = f"REM-{edital.pk:04d}-{obj.pk:05d}"
            obj.save(update_fields=["protocolo", "atualizado_em"])

        registrar_auditoria(
            municipio=municipio,
            modulo="RH",
            evento="REMANEJAMENTO_INSCRICAO_CRIADA",
            entidade="RhRemanejamentoInscricao",
            entidade_id=obj.pk,
            usuario=request.user,
            depois={"edital": edital.numero, "servidor": obj.servidor.nome, "protocolo": obj.protocolo},
        )
        messages.success(request, "Inscrição de remanejamento registrada.")
        return redirect(reverse("rh:remanejamento_edital_detail", args=[edital.pk]) + _q_municipio(municipio))

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova inscrição de remanejamento",
            "subtitle": f"{edital.numero} • {edital.titulo}",
            "form": form,
            "cancel_url": reverse("rh:remanejamento_edital_detail", args=[edital.pk]) + _q_municipio(municipio),
            "submit_label": "Salvar inscrição",
            "enctype": "multipart/form-data",
        },
    )


@login_required
@require_perm("rh.view")
@require_POST
def remanejamento_inscricao_cancelar(request, inscricao_pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    inscricao = get_object_or_404(
        RhRemanejamentoInscricao.objects.select_related("edital", "servidor"),
        pk=inscricao_pk,
        edital__municipio=municipio,
    )
    is_manager = _is_manager(request.user)
    if not is_manager and not _is_owner_inscricao(request.user, inscricao):
        return HttpResponseForbidden("403 — Sem permissão para cancelar esta inscrição.")
    if inscricao.status != RhRemanejamentoInscricao.Status.VALIDA:
        messages.warning(request, "Inscrição já está cancelada.")
        return redirect(reverse("rh:remanejamento_edital_detail", args=[inscricao.edital_id]) + _q_municipio(municipio))
    inscricao.status = RhRemanejamentoInscricao.Status.CANCELADA
    inscricao.motivo_cancelamento = (request.POST.get("motivo") or "").strip() or "Cancelada pelo usuário."
    inscricao.save(update_fields=["status", "motivo_cancelamento", "atualizado_em"])
    messages.success(request, "Inscrição cancelada.")
    return redirect(reverse("rh:remanejamento_edital_detail", args=[inscricao.edital_id]) + _q_municipio(municipio))


@login_required
@require_perm("rh.view")
def remanejamento_recurso_create(request, inscricao_pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    inscricao = get_object_or_404(
        RhRemanejamentoInscricao.objects.select_related("edital", "servidor"),
        pk=inscricao_pk,
        edital__municipio=municipio,
    )
    is_manager = _is_manager(request.user)
    if not is_manager and not _is_owner_inscricao(request.user, inscricao):
        return HttpResponseForbidden("403 — Sem permissão para iniciar recurso desta inscrição.")
    if not is_manager and not inscricao.edital.recurso_aberto:
        return HttpResponseForbidden("403 — O período de recurso não está aberto.")

    form = RhRemanejamentoRecursoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        recurso = form.save(commit=False)
        recurso.inscricao = inscricao
        recurso.criado_por = request.user
        recurso.status = RhRemanejamentoRecurso.Status.PENDENTE
        recurso.save()
        messages.success(request, "Recurso registrado com sucesso.")
        return redirect(reverse("rh:remanejamento_edital_detail", args=[inscricao.edital_id]) + _q_municipio(municipio))

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo recurso de inscrição",
            "subtitle": f"{inscricao.servidor.nome} • {inscricao.edital.numero}",
            "form": form,
            "cancel_url": reverse("rh:remanejamento_edital_detail", args=[inscricao.edital_id]) + _q_municipio(municipio),
            "submit_label": "Enviar recurso",
            "enctype": "multipart/form-data",
        },
    )


@login_required
@require_perm("rh.manage")
@require_POST
def remanejamento_recurso_decidir(request, recurso_pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    recurso = get_object_or_404(
        RhRemanejamentoRecurso.objects.select_related("inscricao", "inscricao__edital"),
        pk=recurso_pk,
        inscricao__edital__municipio=municipio,
    )
    decisao = (request.POST.get("decisao") or "").strip().upper()
    if decisao not in {RhRemanejamentoRecurso.Status.DEFERIDO, RhRemanejamentoRecurso.Status.INDEFERIDO}:
        messages.error(request, "Decisão inválida.")
        return redirect(reverse("rh:remanejamento_edital_detail", args=[recurso.inscricao.edital_id]) + _q_municipio(municipio))

    recurso.status = decisao
    recurso.resposta = (request.POST.get("resposta") or "").strip()
    recurso.respondido_por = request.user
    recurso.respondido_em = timezone.now()
    recurso.save(update_fields=["status", "resposta", "respondido_por", "respondido_em", "atualizado_em"])
    messages.success(request, "Recurso analisado.")
    return redirect(reverse("rh:remanejamento_edital_detail", args=[recurso.inscricao.edital_id]) + _q_municipio(municipio))


@login_required
@require_perm("rh.view")
def substituicao_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    _sync_substituicoes_status(municipio)

    status = (request.GET.get("status") or "").strip()
    q = (request.GET.get("q") or "").strip()
    qs = RhSubstituicaoServidor.objects.filter(municipio=municipio).select_related(
        "substituido", "substituto", "operador", "setor_original_substituto"
    )
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(substituido__nome__icontains=q)
            | Q(substituto__nome__icontains=q)
            | Q(motivo__icontains=q)
        )

    export = (request.GET.get("export") or "").strip().lower()
    if export in {"csv", "pdf"}:
        rows = []
        for item in qs.order_by("-data_inicio", "-id"):
            rows.append(
                [
                    item.substituido.nome,
                    item.substituto.nome,
                    str(item.data_inicio),
                    str(item.data_fim),
                    item.get_status_display(),
                    ", ".join(item.modulos_liberados_json or []),
                ]
            )
        headers = ["Substituido", "Substituto", "Inicio", "Fim", "Status", "Modulos"]
        if export == "csv":
            return export_csv("rh_substituicoes.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="rh_substituicoes.pdf",
            title="Substituições de servidor",
            subtitle=f"{municipio.nome}/{municipio.uf}",
            headers=headers,
            rows=rows,
            filtros=f"Busca={q or '-'} | Status={status or '-'}",
        )

    return render(
        request,
        "rh/substituicao_list.html",
        {
            "title": "Substituição de servidor",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-data_inicio", "-id"),
            "status": status,
            "q": q,
            "status_choices": RhSubstituicaoServidor.Status.choices,
            "actions": [
                *(
                    [
                        {
                            "label": "Nova substituição",
                            "url": reverse("rh:substituicao_create") + _q_municipio(municipio),
                            "icon": "fa-solid fa-plus",
                            "variant": "gp-button--primary",
                        }
                    ]
                    if _is_manager(request.user)
                    else []
                ),
                {
                    "label": "CSV",
                    "url": request.path + f"?municipio={municipio.pk}&q={q}&status={status}&export=csv",
                    "icon": "fa-solid fa-file-csv",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "PDF",
                    "url": request.path + f"?municipio={municipio.pk}&q={q}&status={status}&export=pdf",
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "Painel RH",
                    "url": reverse("rh:index") + _q_municipio(municipio),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("rh.manage")
def substituicao_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para adicionar substituição.")
        return redirect("rh:substituicao_list")

    form = RhSubstituicaoServidorForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.operador = request.user
        obj.setor_original_substituto = obj.substituto.setor
        obj.save()
        form.save_m2m()
        obj.sync_status()
        messages.success(request, "Substituição cadastrada.")
        return redirect(reverse("rh:substituicao_detail", args=[obj.pk]) + _q_municipio(municipio))

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova substituição de servidor",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "form": form,
            "cancel_url": reverse("rh:substituicao_list") + _q_municipio(municipio),
            "submit_label": "Salvar substituição",
        },
    )


@login_required
@require_perm("rh.view")
def substituicao_detail(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    item = get_object_or_404(
        RhSubstituicaoServidor.objects.select_related("substituido", "substituto", "operador", "setor_original_substituto").prefetch_related(
            "setores_liberados"
        ),
        pk=pk,
        municipio=municipio,
    )
    item.sync_status()
    return render(
        request,
        "rh/substituicao_detail.html",
        {
            "title": "Detalhes da substituição",
            "subtitle": f"{item.substituto.nome} substitui {item.substituido.nome}",
            "municipio": municipio,
            "item": item,
            "is_manager": _is_manager(request.user),
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("rh:substituicao_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                }
            ],
        },
    )


@login_required
@require_perm("rh.manage")
@require_POST
def substituicao_cancelar(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    item = get_object_or_404(RhSubstituicaoServidor, pk=pk, municipio=municipio)
    item.status = RhSubstituicaoServidor.Status.CANCELADA
    item.save(update_fields=["status", "atualizado_em"])
    messages.success(request, "Substituição cancelada.")
    return redirect(reverse("rh:substituicao_detail", args=[item.pk]) + _q_municipio(municipio))


@login_required
@require_perm("rh.view")
def pdp_plano_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    ano = (request.GET.get("ano") or "").strip()
    status = (request.GET.get("status") or "").strip()
    qs = RhPdpPlano.objects.filter(municipio=municipio).annotate(total_necessidades=Count("necessidades"))
    if ano.isdigit():
        qs = qs.filter(ano=int(ano))
    if status:
        qs = qs.filter(status=status)

    export = (request.GET.get("export") or "").strip().lower()
    if export in {"csv", "pdf"}:
        rows = []
        for item in qs.order_by("-ano", "-id"):
            rows.append(
                [
                    str(item.ano),
                    item.titulo or f"PDP {item.ano}",
                    item.get_status_display(),
                    str(item.total_necessidades),
                    str(item.aprovado_em or ""),
                    str(item.enviado_sipec_em or ""),
                ]
            )
        headers = ["Ano", "Titulo", "Status", "Necessidades", "Aprovado em", "SIPEC em"]
        if export == "csv":
            return export_csv("rh_pdp_planos.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="rh_pdp_planos.pdf",
            title="PDP - Planos",
            subtitle=f"{municipio.nome}/{municipio.uf}",
            headers=headers,
            rows=rows,
            filtros=f"Ano={ano or '-'} | Status={status or '-'}",
        )

    return render(
        request,
        "rh/pdp_plano_list.html",
        {
            "title": "Plano de Desenvolvimento de Pessoas (PDP)",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-ano", "-id"),
            "ano": ano,
            "status": status,
            "status_choices": RhPdpPlano.Status.choices,
            "actions": [
                *(
                    [
                        {
                            "label": "Novo plano",
                            "url": reverse("rh:pdp_plano_create") + _q_municipio(municipio),
                            "icon": "fa-solid fa-plus",
                            "variant": "gp-button--primary",
                        }
                    ]
                    if _is_manager(request.user)
                    else []
                ),
                {
                    "label": "CSV",
                    "url": request.path + f"?municipio={municipio.pk}&ano={ano}&status={status}&export=csv",
                    "icon": "fa-solid fa-file-csv",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "PDF",
                    "url": request.path + f"?municipio={municipio.pk}&ano={ano}&status={status}&export=pdf",
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "Painel RH",
                    "url": reverse("rh:index") + _q_municipio(municipio),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("rh.manage")
def pdp_plano_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para adicionar plano PDP.")
        return redirect("rh:pdp_plano_list")

    form = RhPdpPlanoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        if not obj.titulo:
            obj.titulo = f"PDP {obj.ano} - {municipio.nome}"
        obj.save()
        messages.success(request, "Plano PDP criado.")
        return redirect(reverse("rh:pdp_plano_detail", args=[obj.pk]) + _q_municipio(municipio))

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo plano PDP",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "form": form,
            "cancel_url": reverse("rh:pdp_plano_list") + _q_municipio(municipio),
            "submit_label": "Salvar plano",
        },
    )


@login_required
@require_perm("rh.view")
def pdp_plano_detail(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    plano = get_object_or_404(RhPdpPlano, pk=pk, municipio=municipio)
    status = (request.GET.get("status") or "").strip()
    tipo = (request.GET.get("tipo") or "").strip()

    necessidades = RhPdpNecessidade.objects.filter(plano=plano).select_related("servidor", "setor_lotacao")
    if status:
        necessidades = necessidades.filter(status=status)
    if tipo:
        necessidades = necessidades.filter(tipo_submissao=tipo)
    necessidades = necessidades.order_by("-criado_em", "-id")

    return render(
        request,
        "rh/pdp_plano_detail.html",
        {
            "title": plano.titulo or f"PDP {plano.ano}",
            "subtitle": f"Ano {plano.ano}",
            "municipio": municipio,
            "plano": plano,
            "is_manager": _is_manager(request.user),
            "necessidades": necessidades,
            "status": status,
            "tipo": tipo,
            "status_choices": RhPdpNecessidade.Status.choices,
            "tipo_choices": RhPdpNecessidade.TipoSubmissao.choices,
            "cards": [
                {"label": "Total de necessidades", "value": necessidades.count()},
                {"label": "Enviadas", "value": necessidades.filter(status=RhPdpNecessidade.Status.ENVIADA).count()},
                {"label": "Aprovadas local", "value": necessidades.filter(status=RhPdpNecessidade.Status.APROVADA_LOCAL).count()},
                {"label": "Aprovadas central", "value": necessidades.filter(status=RhPdpNecessidade.Status.APROVADA_CENTRAL).count()},
            ],
            "actions": [
                {
                    "label": "Nova necessidade",
                    "url": reverse("rh:pdp_necessidade_create", args=[plano.pk]) + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "gp-button--primary",
                },
                {
                    "label": "Voltar",
                    "url": reverse("rh:pdp_plano_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("rh.view")
def pdp_necessidade_create(request, plano_pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    plano = get_object_or_404(RhPdpPlano, pk=plano_pk, municipio=municipio)
    is_manager = _is_manager(request.user)

    if plano.status not in {RhPdpPlano.Status.COLETA, RhPdpPlano.Status.APROVACAO_LOCAL} and not is_manager:
        return HttpResponseForbidden("403 — O plano não está recebendo novas necessidades no momento.")

    form = RhPdpNecessidadeForm(request.POST or None, municipio=municipio, is_manager=is_manager)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.plano = plano
        obj.municipio = municipio
        obj.servidor = request.user
        if not is_manager:
            obj.tipo_submissao = RhPdpNecessidade.TipoSubmissao.INDIVIDUAL
        obj.status = RhPdpNecessidade.Status.ENVIADA
        obj.criado_por = request.user
        if not obj.custo_individual_previsto:
            obj.custo_individual_previsto = Decimal("0")
        obj.save()
        messages.success(request, "Necessidade PDP enviada com sucesso.")
        return redirect(reverse("rh:pdp_plano_detail", args=[plano.pk]) + _q_municipio(municipio))

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova necessidade PDP",
            "subtitle": f"{plano.titulo or plano.ano}",
            "form": form,
            "cancel_url": reverse("rh:pdp_plano_detail", args=[plano.pk]) + _q_municipio(municipio),
            "submit_label": "Enviar necessidade",
        },
    )


@login_required
@require_perm("rh.manage")
@require_POST
def pdp_necessidade_status(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    item = get_object_or_404(RhPdpNecessidade, pk=pk, municipio=municipio)
    action = (request.POST.get("acao") or "").strip().lower()
    parecer = (request.POST.get("parecer") or "").strip()

    if action == "aprovar_local":
        item.status = RhPdpNecessidade.Status.APROVADA_LOCAL
        item.analise_local_parecer = parecer
        item.analisado_local_por = request.user
        item.analisado_local_em = timezone.now()
        fields = ["status", "analise_local_parecer", "analisado_local_por", "analisado_local_em", "atualizado_em"]
    elif action == "rejeitar_local":
        item.status = RhPdpNecessidade.Status.REJEITADA_LOCAL
        item.analise_local_parecer = parecer
        item.analisado_local_por = request.user
        item.analisado_local_em = timezone.now()
        fields = ["status", "analise_local_parecer", "analisado_local_por", "analisado_local_em", "atualizado_em"]
    elif action == "consolidar_central":
        item.status = RhPdpNecessidade.Status.CONSOLIDADA_CENTRAL
        item.analise_central_parecer = parecer
        item.analisado_central_por = request.user
        item.analisado_central_em = timezone.now()
        fields = ["status", "analise_central_parecer", "analisado_central_por", "analisado_central_em", "atualizado_em"]
    elif action == "aprovar_central":
        item.status = RhPdpNecessidade.Status.APROVADA_CENTRAL
        item.analise_central_parecer = parecer
        item.analisado_central_por = request.user
        item.analisado_central_em = timezone.now()
        fields = ["status", "analise_central_parecer", "analisado_central_por", "analisado_central_em", "atualizado_em"]
    else:
        messages.error(request, "Ação de status inválida.")
        return redirect(reverse("rh:pdp_plano_detail", args=[item.plano_id]) + _q_municipio(municipio))

    item.save(update_fields=fields)
    messages.success(request, "Status da necessidade atualizado.")
    return redirect(reverse("rh:pdp_plano_detail", args=[item.plano_id]) + _q_municipio(municipio))


@login_required
@require_perm("rh.manage")
@require_POST
def pdp_plano_exportar_sipec(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    plano = get_object_or_404(RhPdpPlano, pk=pk, municipio=municipio)
    plano.status = RhPdpPlano.Status.EXPORTADO_SIPEC
    plano.enviado_sipec_em = timezone.now()
    plano.aprovado_por_autoridade = request.user
    plano.aprovado_em = timezone.now()
    plano.save(update_fields=["status", "enviado_sipec_em", "aprovado_por_autoridade", "aprovado_em", "atualizado_em"])
    messages.success(request, "Plano marcado como exportado para SIPEC.")
    return redirect(reverse("rh:pdp_plano_detail", args=[plano.pk]) + _q_municipio(municipio))
