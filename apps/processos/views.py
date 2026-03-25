from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.exports import export_csv, export_pdf_table
from apps.core.decorators import require_perm
from apps.core.rbac import is_admin
from apps.core.services_registro_operacao import build_registro_context
from apps.core.services_auditoria import registrar_auditoria
from apps.core.services_transparencia import publicar_evento_transparencia
from apps.org.models import Municipio

from .forms import ProcessoAdministrativoForm, ProcessoAndamentoForm
from .models import ProcessoAdministrativo


def _resolve_municipio(request, *, require_selected: bool = False):
    user = request.user
    if is_admin(user):
        municipio_id = (request.GET.get("municipio") or request.POST.get("municipio") or "").strip()
        if municipio_id.isdigit():
            return Municipio.objects.filter(pk=int(municipio_id), ativo=True).first()
        if require_selected:
            return None
        return Municipio.objects.filter(ativo=True).order_by("nome").first()

    profile = getattr(user, "profile", None)
    if profile and profile.municipio_id:
        return Municipio.objects.filter(pk=profile.municipio_id, ativo=True).first()
    return None


def _municipios_admin(request):
    if not is_admin(request.user):
        return Municipio.objects.none()
    return Municipio.objects.filter(ativo=True).order_by("nome")


@login_required
@require_perm("processos.view")
def index(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        messages.error(request, "Selecione um municipio para acessar Processos.")
        return redirect("core:dashboard")
    return redirect(reverse("processos:list") + f"?municipio={municipio.pk}")


@login_required
@require_perm("processos.view")
def processo_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    tipo = (request.GET.get("tipo") or "").strip()

    qs = ProcessoAdministrativo.objects.filter(municipio=municipio).select_related(
        "secretaria", "unidade", "setor", "responsavel_atual"
    )
    if q:
        qs = qs.filter(
            Q(numero__icontains=q)
            | Q(assunto__icontains=q)
            | Q(tipo__icontains=q)
            | Q(solicitante_nome__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)
    if tipo:
        qs = qs.filter(tipo__icontains=tipo)

    export = (request.GET.get("export") or "").strip().lower()
    if export in {"csv", "pdf"}:
        rows = []
        for item in qs.order_by("-criado_em"):
            rows.append(
                [
                    item.numero,
                    item.tipo,
                    item.assunto,
                    item.get_status_display(),
                    item.solicitante_nome or "-",
                    str(item.data_abertura or ""),
                    str(item.prazo_final or ""),
                ]
            )
        headers = ["Numero", "Tipo", "Assunto", "Status", "Solicitante", "Abertura", "Prazo"]
        if export == "csv":
            return export_csv("processos.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="processos.pdf",
            title="Processos administrativos",
            subtitle=f"{municipio.nome}/{municipio.uf}",
            headers=headers,
            rows=rows,
            filtros=f"Busca={q or '-'} | Status={status or '-'} | Tipo={tipo or '-'}",
        )

    return render(
        request,
        "processos/list.html",
        {
            "title": "Protocolo e Processos",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-criado_em"),
            "q": q,
            "status": status,
            "tipo": tipo,
            "status_choices": ProcessoAdministrativo.Status.choices,
            "actions": [
                {
                    "label": "Novo processo",
                    "url": reverse("processos:create") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-plus",
                    "variant": "gp-button--primary",
                },
                {
                    "label": "Portal",
                    "url": reverse("portal"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "CSV",
                    "url": request.path + f"?municipio={municipio.pk}&q={q}&status={status}&tipo={tipo}&export=csv",
                    "icon": "fa-solid fa-file-csv",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "PDF",
                    "url": request.path + f"?municipio={municipio.pk}&q={q}&status={status}&tipo={tipo}&export=pdf",
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "gp-button--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("processos.manage")
def processo_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um municipio para criar processo.")
        return redirect("processos:list")

    form = ProcessoAdministrativoForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        registrar_auditoria(
            municipio=municipio,
            modulo="PROCESSOS",
            evento="PROCESSO_CRIADO",
            entidade="ProcessoAdministrativo",
            entidade_id=obj.pk,
            usuario=request.user,
            depois={
                "numero": obj.numero,
                "tipo": obj.tipo,
                "status": obj.status,
                "data_abertura": str(obj.data_abertura),
            },
        )
        publicar_evento_transparencia(
            municipio=municipio,
            modulo="PROCESSOS",
            tipo_evento="PROCESSO_CRIADO",
            titulo=f"Processo {obj.numero} cadastrado",
            descricao=obj.assunto,
            referencia=obj.numero,
            dados={
                "tipo": obj.tipo,
                "status": obj.status,
                "solicitante": obj.solicitante_nome,
            },
        )
        messages.success(request, "Processo criado com sucesso.")
        return redirect(reverse("processos:detail", args=[obj.pk]) + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo processo",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("processos:list") + f"?municipio={municipio.pk}",
            "submit_label": "Salvar processo",
        },
    )


@login_required
@require_perm("processos.view")
def processo_detail(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    processo = get_object_or_404(
        ProcessoAdministrativo.objects.select_related("secretaria", "unidade", "setor", "responsavel_atual"),
        pk=pk,
        municipio=municipio,
    )

    fields = [
        {"label": "Numero", "value": processo.numero},
        {"label": "Tipo", "value": processo.tipo},
        {"label": "Assunto", "value": processo.assunto},
        {"label": "Solicitante", "value": processo.solicitante_nome or "-"},
        {"label": "Secretaria", "value": processo.secretaria or "-"},
        {"label": "Unidade", "value": processo.unidade or "-"},
        {"label": "Setor", "value": processo.setor or "-"},
        {"label": "Responsavel", "value": processo.responsavel_atual or "-"},
    ]
    pills = [
        {"label": "Status", "value": processo.get_status_display()},
        {"label": "Data abertura", "value": processo.data_abertura},
        {"label": "Prazo", "value": processo.prazo_final or "-"},
    ]

    checklist = [
        {"label": "Numero informado", "ok": bool(processo.numero)},
        {"label": "Tipo informado", "ok": bool(processo.tipo)},
        {"label": "Assunto informado", "ok": bool(processo.assunto)},
        {"label": "Setor de origem definido", "ok": bool(processo.setor_id)},
        {"label": "Responsavel atual definido", "ok": bool(processo.responsavel_atual_id)},
    ]
    registro = build_registro_context(
        municipio=municipio,
        modulo="PROCESSOS",
        entidade="ProcessoAdministrativo",
        entidade_id=processo.pk,
    )

    return render(
        request,
        "processos/detail.html",
        {
            "title": f"Processo {processo.numero}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [
                {
                    "label": "Adicionar andamento",
                    "url": reverse("processos:andamento_create", args=[processo.pk]) + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-route",
                    "variant": "gp-button--primary",
                },
                {
                    "label": "Voltar",
                    "url": reverse("processos:list") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                },
            ],
            "obj": processo,
            "fields": fields,
            "pills": pills,
            "andamentos": processo.andamentos.select_related("setor_origem", "setor_destino", "criado_por").order_by("-data_evento", "-id"),
            "municipio": municipio,
            "checklist_conformidade": checklist,
            **registro,
        },
    )


@login_required
@require_perm("processos.manage")
def andamento_create(request, processo_pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    processo = get_object_or_404(ProcessoAdministrativo, pk=processo_pk, municipio=municipio)
    form = ProcessoAndamentoForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.processo = processo
        obj.criado_por = request.user
        obj.save()

        if obj.tipo == obj.Tipo.CONCLUSAO:
            processo.status = ProcessoAdministrativo.Status.CONCLUIDO
            processo.save(update_fields=["status", "atualizado_em"])

        registrar_auditoria(
            municipio=municipio,
            modulo="PROCESSOS",
            evento="PROCESSO_ANDAMENTO_REGISTRADO",
            entidade="ProcessoAndamento",
            entidade_id=obj.pk,
            usuario=request.user,
            depois={
                "processo_numero": processo.numero,
                "tipo": obj.tipo,
                "data_evento": str(obj.data_evento),
                "status_processo": processo.status,
            },
        )
        publicar_evento_transparencia(
            municipio=municipio,
            modulo="PROCESSOS",
            tipo_evento="PROCESSO_ANDAMENTO",
            titulo=f"Andamento registrado no processo {processo.numero}",
            descricao=f"Tipo: {obj.get_tipo_display()}",
            referencia=processo.numero,
            dados={
                "tipo": obj.tipo,
                "status_processo": processo.status,
                "setor_destino_id": obj.setor_destino_id,
            },
        )

        messages.success(request, "Andamento registrado com sucesso.")
        return redirect(reverse("processos:detail", args=[processo.pk]) + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Novo andamento - Processo {processo.numero}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("processos:detail", args=[processo.pk]) + f"?municipio={municipio.pk}",
            "submit_label": "Salvar andamento",
        },
    )
