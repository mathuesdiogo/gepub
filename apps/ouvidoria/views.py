from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import require_perm
from apps.core.services_auditoria import registrar_auditoria
from apps.core.services_transparencia import publicar_evento_transparencia
from apps.core.rbac import is_admin
from apps.org.models import Municipio

from .forms import OuvidoriaCadastroForm, OuvidoriaRespostaForm, OuvidoriaTramitacaoForm
from .models import OuvidoriaCadastro, OuvidoriaResposta, OuvidoriaTramitacao


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


def _q_municipio(municipio: Municipio) -> str:
    return f"?municipio={municipio.pk}"


@login_required
@require_perm("ouvidoria.view")
def index(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    chamados = OuvidoriaCadastro.objects.filter(municipio=municipio)
    return render(
        request,
        "ouvidoria/index.html",
        {
            "title": "Ouvidoria e e-SIC",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "cards": [
                {"label": "Chamados abertos", "value": chamados.filter(status=OuvidoriaCadastro.Status.ABERTO).count()},
                {"label": "Em análise", "value": chamados.filter(status=OuvidoriaCadastro.Status.EM_ANALISE).count()},
                {"label": "Encaminhados", "value": chamados.filter(status=OuvidoriaCadastro.Status.ENCAMINHADO).count()},
                {"label": "Concluídos", "value": chamados.filter(status=OuvidoriaCadastro.Status.CONCLUIDO).count()},
            ],
            "items": chamados.select_related("secretaria", "setor").order_by("-criado_em")[:15],
            "status_choices": OuvidoriaCadastro.Status.choices,
            "actions": [
                {
                    "label": "Novo chamado",
                    "url": reverse("ouvidoria:chamado_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Tramitações",
                    "url": reverse("ouvidoria:tramitacao_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-right-left",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Respostas",
                    "url": reverse("ouvidoria:resposta_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-reply",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("ouvidoria.view")
def chamado_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    tipo = (request.GET.get("tipo") or "").strip()
    qs = OuvidoriaCadastro.objects.filter(municipio=municipio).select_related("secretaria", "unidade", "setor")
    if q:
        qs = qs.filter(Q(protocolo__icontains=q) | Q(assunto__icontains=q) | Q(solicitante_nome__icontains=q))
    if status:
        qs = qs.filter(status=status)
    if tipo:
        qs = qs.filter(tipo=tipo)
    return render(
        request,
        "ouvidoria/chamado_list.html",
        {
            "title": "Chamados",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-criado_em"),
            "q": q,
            "status": status,
            "tipo": tipo,
            "status_choices": OuvidoriaCadastro.Status.choices,
            "tipo_choices": OuvidoriaCadastro.Tipo.choices,
            "actions": [
                {
                    "label": "Novo chamado",
                    "url": reverse("ouvidoria:chamado_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            ],
        },
    )


@login_required
@require_perm("ouvidoria.manage")
def chamado_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para criar chamado.")
        return redirect("ouvidoria:chamado_list")
    form = OuvidoriaCadastroForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.status = OuvidoriaCadastro.Status.ABERTO
        obj.save()
        publicar_evento_transparencia(
            municipio=municipio,
            modulo="OUVIDORIA",
            tipo_evento="CHAMADO_ABERTO",
            titulo=f"Chamado {obj.protocolo} aberto",
            descricao=obj.assunto,
            referencia=obj.protocolo,
            dados={"tipo": obj.tipo, "prioridade": obj.prioridade},
            publico=False,
        )
        messages.success(request, "Chamado registrado.")
        return redirect(reverse("ouvidoria:chamado_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo chamado de ouvidoria",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("ouvidoria:chamado_list") + _q_municipio(municipio),
            "submit_label": "Salvar chamado",
        },
    )


@login_required
@require_perm("ouvidoria.manage")
@require_POST
def chamado_concluir(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(OuvidoriaCadastro, pk=pk, municipio=municipio)
    obj.status = OuvidoriaCadastro.Status.CONCLUIDO
    obj.respondido_por = request.user
    obj.respondido_em = timezone.now()
    obj.save(update_fields=["status", "respondido_por", "respondido_em", "atualizado_em"])
    messages.success(request, "Chamado concluído.")
    return redirect(reverse("ouvidoria:chamado_list") + _q_municipio(municipio))


@login_required
@require_perm("ouvidoria.view")
def tramitacao_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    qs = OuvidoriaTramitacao.objects.filter(municipio=municipio).select_related("chamado", "setor_origem", "setor_destino")
    return render(
        request,
        "ouvidoria/tramitacao_list.html",
        {
            "title": "Tramitações de chamados",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-criado_em"),
            "actions": [
                {
                    "label": "Nova tramitação",
                    "url": reverse("ouvidoria:tramitacao_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            ],
        },
    )


@login_required
@require_perm("ouvidoria.manage")
def tramitacao_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para tramitar chamado.")
        return redirect("ouvidoria:tramitacao_list")
    form = OuvidoriaTramitacaoForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        chamado = obj.chamado
        chamado.status = OuvidoriaCadastro.Status.ENCAMINHADO
        chamado.save(update_fields=["status", "atualizado_em"])
        messages.success(request, "Tramitação registrada.")
        return redirect(reverse("ouvidoria:tramitacao_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova tramitação",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("ouvidoria:tramitacao_list") + _q_municipio(municipio),
            "submit_label": "Salvar tramitação",
        },
    )


@login_required
@require_perm("ouvidoria.view")
def resposta_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    qs = OuvidoriaResposta.objects.filter(municipio=municipio).select_related("chamado", "criado_por")
    return render(
        request,
        "ouvidoria/resposta_list.html",
        {
            "title": "Respostas aos chamados",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-criado_em"),
            "actions": [
                {
                    "label": "Nova resposta",
                    "url": reverse("ouvidoria:resposta_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            ],
        },
    )


@login_required
@require_perm("ouvidoria.manage")
def resposta_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para responder chamado.")
        return redirect("ouvidoria:resposta_list")
    form = OuvidoriaRespostaForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        chamado = obj.chamado
        chamado.status = OuvidoriaCadastro.Status.RESPONDIDO
        chamado.respondido_por = request.user
        chamado.respondido_em = timezone.now()
        chamado.save(update_fields=["status", "respondido_por", "respondido_em", "atualizado_em"])
        registrar_auditoria(
            municipio=municipio,
            modulo="OUVIDORIA",
            evento="RESPOSTA_REGISTRADA",
            entidade="OuvidoriaResposta",
            entidade_id=obj.pk,
            usuario=request.user,
            depois={"protocolo": chamado.protocolo, "publico": obj.publico},
        )
        messages.success(request, "Resposta registrada.")
        return redirect(reverse("ouvidoria:resposta_list") + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova resposta de ouvidoria",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("ouvidoria:resposta_list") + _q_municipio(municipio),
            "submit_label": "Salvar resposta",
        },
    )


# compatibilidade com rota antiga
create = chamado_create
