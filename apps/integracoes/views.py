from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
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

    return render(
        request,
        "integracoes/index.html",
        {
            "title": "Hub de Integracoes",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "q": q,
            "conectores": conectores.order_by("nome"),
            "execucoes": execucoes.order_by("-executado_em", "-id")[:100],
            "actions": [
                {
                    "label": "Novo conector",
                    "url": reverse("integracoes:conector_create") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-plug-circle-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Registrar execucao",
                    "url": reverse("integracoes:execucao_create") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-cloud-arrow-up",
                    "variant": "btn--ghost",
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
