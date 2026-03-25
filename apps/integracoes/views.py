from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import require_perm
from apps.core.exports import export_csv, export_pdf_table
from apps.core.rbac import is_admin
from apps.core.services_auditoria import registrar_auditoria
from apps.core.services_transparencia import publicar_evento_transparencia
from apps.org.models import Municipio

from .forms import ConectorIntegracaoForm, IntegracaoExecucaoForm
from .models import ConectorIntegracao, IntegracaoExecucao


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
@require_perm("integracoes.view")
def index(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    conectores = ConectorIntegracao.objects.filter(municipio=municipio)
    execucoes = IntegracaoExecucao.objects.filter(municipio=municipio).select_related("conector")
    if q:
        conectores = conectores.filter(Q(nome__icontains=q) | Q(dominio__icontains=q) | Q(endpoint__icontains=q))
        execucoes = execucoes.filter(Q(referencia__icontains=q) | Q(conector__nome__icontains=q))

    latest_exec_by_conector = {}
    for item in execucoes.order_by("conector_id", "-executado_em", "-id"):
        if item.conector_id not in latest_exec_by_conector:
            latest_exec_by_conector[item.conector_id] = item
    now = timezone.now()
    conector_rows = []
    for item in conectores.order_by("nome"):
        latest = latest_exec_by_conector.get(item.id)
        health = "SEM_EXECUCAO"
        if latest:
            delta = now - latest.executado_em
            if latest.status == IntegracaoExecucao.Status.FALHA:
                health = "ERRO"
            elif delta.total_seconds() > 72 * 3600:
                health = "ATRASADO"
            else:
                health = "OK"
        conector_rows.append((item, latest, health))

    export = (request.GET.get("export") or "").strip().lower()
    export_scope = (request.GET.get("scope") or "conectores").strip().lower()
    if export in {"csv", "pdf"}:
        if export_scope == "execucoes":
            rows = []
            for item in execucoes.order_by("-executado_em", "-id")[:1000]:
                rows.append(
                    [
                        str(item.executado_em),
                        item.conector.nome,
                        item.get_direcao_display(),
                        item.get_status_display(),
                        str(item.quantidade_registros),
                        item.referencia or "",
                    ]
                )
            headers = ["Executado em", "Conector", "Direcao", "Status", "Registros", "Referencia"]
            if export == "csv":
                return export_csv("integracoes_execucoes.csv", headers, rows)
            return export_pdf_table(
                request,
                filename="integracoes_execucoes.pdf",
                title="Execucoes de integracao",
                subtitle=f"{municipio.nome}/{municipio.uf}",
                headers=headers,
                rows=rows,
                filtros=f"Busca={q or '-'}",
            )

        rows = []
        for item, latest, health in conector_rows:
            rows.append(
                [
                    item.nome,
                    item.get_dominio_display(),
                    item.get_tipo_display(),
                    item.endpoint or "",
                    "SIM" if item.ativo else "NAO",
                    health,
                    str(latest.executado_em) if latest else "",
                    latest.get_status_display() if latest else "",
                ]
            )
        headers = ["Nome", "Dominio", "Tipo", "Endpoint", "Ativo", "Saude", "Ultima execucao", "Status ultima execucao"]
        if export == "csv":
            return export_csv("integracoes_conectores.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="integracoes_conectores.pdf",
            title="Conectores de integracao",
            subtitle=f"{municipio.nome}/{municipio.uf}",
            headers=headers,
            rows=rows,
            filtros=f"Busca={q or '-'}",
        )

    health_counts = {"ok": 0, "erro": 0, "atrasado": 0, "sem_execucao": 0}
    for _item, _latest, health in conector_rows:
        if health == "OK":
            health_counts["ok"] += 1
        elif health == "ERRO":
            health_counts["erro"] += 1
        elif health == "ATRASADO":
            health_counts["atrasado"] += 1
        else:
            health_counts["sem_execucao"] += 1

    return render(
        request,
        "integracoes/index.html",
        {
            "title": "Hub de Integracoes",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "q": q,
            "conectores": conector_rows,
            "execucoes": execucoes.order_by("-executado_em", "-id")[:100],
            "health_counts": health_counts,
            "actions": [
                {
                    "label": "Novo conector",
                    "url": reverse("integracoes:conector_create") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-plug-circle-plus",
                    "variant": "gp-button--primary",
                },
                {
                    "label": "Registrar execucao",
                    "url": reverse("integracoes:execucao_create") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-cloud-arrow-up",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "CSV conectores",
                    "url": request.path + f"?municipio={municipio.pk}&q={q}&scope=conectores&export=csv",
                    "icon": "fa-solid fa-file-csv",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "CSV execucoes",
                    "url": request.path + f"?municipio={municipio.pk}&q={q}&scope=execucoes&export=csv",
                    "icon": "fa-solid fa-file-csv",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "PDF conectores",
                    "url": request.path + f"?municipio={municipio.pk}&q={q}&scope=conectores&export=pdf",
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "PDF execucoes",
                    "url": request.path + f"?municipio={municipio.pk}&q={q}&scope=execucoes&export=pdf",
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "gp-button--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("integracoes.admin")
def conector_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um municipio para criar conector.")
        return redirect("integracoes:index")

    form = ConectorIntegracaoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        registrar_auditoria(
            municipio=municipio,
            modulo="INTEGRACOES",
            evento="CONECTOR_CRIADO",
            entidade="ConectorIntegracao",
            entidade_id=obj.pk,
            usuario=request.user,
            depois={
                "nome": obj.nome,
                "dominio": obj.dominio,
                "tipo": obj.tipo,
                "ativo": obj.ativo,
            },
        )
        publicar_evento_transparencia(
            municipio=municipio,
            modulo="INTEGRACOES",
            tipo_evento="CONECTOR_CRIADO",
            titulo=f"Conector {obj.nome} cadastrado",
            descricao=f"Dominio: {obj.get_dominio_display()}",
            referencia=obj.nome,
            dados={"tipo": obj.tipo, "ativo": obj.ativo},
            publico=False,
        )
        messages.success(request, "Conector criado com sucesso.")
        return redirect(reverse("integracoes:index") + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo conector",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("integracoes:index") + f"?municipio={municipio.pk}",
            "submit_label": "Salvar conector",
        },
    )


@login_required
@require_perm("integracoes.manage")
def execucao_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um municipio para registrar execucao.")
        return redirect("integracoes:index")

    form = IntegracaoExecucaoForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.executado_por = request.user
        obj.save()
        registrar_auditoria(
            municipio=municipio,
            modulo="INTEGRACOES",
            evento="EXECUCAO_REGISTRADA",
            entidade="IntegracaoExecucao",
            entidade_id=obj.pk,
            usuario=request.user,
            depois={
                "conector": obj.conector.nome,
                "status": obj.status,
                "direcao": obj.direcao,
                "quantidade_registros": obj.quantidade_registros,
            },
        )
        publicar_evento_transparencia(
            municipio=municipio,
            modulo="INTEGRACOES",
            tipo_evento="EXECUCAO_INTEGRACAO",
            titulo=f"Execucao de integracao {obj.conector.nome}",
            descricao=f"Status: {obj.get_status_display()}",
            referencia=obj.referencia or str(obj.pk),
            dados={
                "status": obj.status,
                "direcao": obj.direcao,
                "quantidade_registros": obj.quantidade_registros,
            },
            publico=False,
        )
        messages.success(request, "Execucao registrada com sucesso.")
        return redirect(reverse("integracoes:index") + f"?municipio={municipio.pk}")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Registrar execucao",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("integracoes:index") + f"?municipio={municipio.pk}",
            "submit_label": "Salvar execucao",
        },
    )


@login_required
@require_perm("integracoes.manage")
@require_POST
def execucao_reprocessar(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    origem = IntegracaoExecucao.objects.select_related("conector").filter(pk=pk, municipio=municipio).first()
    if not origem:
        messages.error(request, "Execucao de origem nao encontrada.")
        return redirect(reverse("integracoes:index") + f"?municipio={municipio.pk}")

    nova = IntegracaoExecucao.objects.create(
        municipio=municipio,
        conector=origem.conector,
        direcao=origem.direcao,
        status=IntegracaoExecucao.Status.SUCESSO,
        referencia=f"REPROCESSO-{origem.pk}",
        quantidade_registros=origem.quantidade_registros,
        detalhes=(origem.detalhes or "")[:3500],
        executado_por=request.user,
    )
    registrar_auditoria(
        municipio=municipio,
        modulo="INTEGRACOES",
        evento="EXECUCAO_REPROCESSADA",
        entidade="IntegracaoExecucao",
        entidade_id=nova.pk,
        usuario=request.user,
        depois={
            "origem_id": origem.pk,
            "conector": origem.conector.nome,
            "referencia": nova.referencia,
        },
    )
    messages.success(request, f"Reprocessamento registrado a partir da execução #{origem.pk}.")
    return redirect(reverse("integracoes:index") + f"?municipio={municipio.pk}")
