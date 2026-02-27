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

from .forms import RhCadastroForm, RhDocumentoForm, RhMovimentacaoForm
from .models import RhCadastro, RhDocumento, RhMovimentacao


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
@require_perm("rh.view")
def index(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    servidores_qs = RhCadastro.objects.filter(municipio=municipio)
    mov_qs = RhMovimentacao.objects.filter(municipio=municipio)
    docs_qs = RhDocumento.objects.filter(municipio=municipio)

    return render(
        request,
        "rh/index.html",
        {
            "title": "RH e Vida Funcional",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "cards": [
                {"label": "Servidores ativos", "value": servidores_qs.filter(status=RhCadastro.Status.ATIVO).count()},
                {
                    "label": "Férias/Afastamentos",
                    "value": servidores_qs.filter(
                        situacao_funcional__in=[RhCadastro.SituacaoFuncional.FERIAS, RhCadastro.SituacaoFuncional.AFASTADO]
                    ).count(),
                },
                {"label": "Movimentações pendentes", "value": mov_qs.filter(status=RhMovimentacao.Status.PENDENTE).count()},
                {"label": "Documentos funcionais", "value": docs_qs.count()},
            ],
            "latest_movimentacoes": mov_qs.select_related("servidor").order_by("-data_inicio", "-id")[:10],
            "latest_documentos": docs_qs.select_related("servidor").order_by("-data_documento", "-id")[:10],
            "actions": [
                {
                    "label": "Novo servidor",
                    "url": reverse("rh:servidor_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-user-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Movimentações",
                    "url": reverse("rh:movimentacao_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-right-left",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Documentos",
                    "url": reverse("rh:documento_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-folder-open",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("rh.view")
def servidor_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    situacao = (request.GET.get("situacao") or "").strip()
    status = (request.GET.get("status") or "").strip()

    qs = RhCadastro.objects.filter(municipio=municipio).select_related("secretaria", "unidade", "setor", "servidor")
    if q:
        qs = qs.filter(
            Q(codigo__icontains=q)
            | Q(matricula__icontains=q)
            | Q(nome__icontains=q)
            | Q(cargo__icontains=q)
            | Q(funcao__icontains=q)
        )
    if situacao:
        qs = qs.filter(situacao_funcional=situacao)
    if status:
        qs = qs.filter(status=status)

    return render(
        request,
        "rh/servidor_list.html",
        {
            "title": "Servidores funcionais",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("nome"),
            "q": q,
            "situacao": situacao,
            "status": status,
            "status_choices": RhCadastro.Status.choices,
            "situacao_choices": RhCadastro.SituacaoFuncional.choices,
            "actions": [
                {
                    "label": "Novo servidor",
                    "url": reverse("rh:servidor_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Painel RH",
                    "url": reverse("rh:index") + _q_municipio(municipio),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("rh.manage")
def servidor_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para criar servidor.")
        return redirect("rh:servidor_list")

    form = RhCadastroForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()

        registrar_auditoria(
            municipio=municipio,
            modulo="RH",
            evento="SERVIDOR_FUNCIONAL_CRIADO",
            entidade="RhCadastro",
            entidade_id=obj.pk,
            usuario=request.user,
            depois={
                "codigo": obj.codigo,
                "matricula": obj.matricula,
                "nome": obj.nome,
                "cargo": obj.cargo,
                "situacao": obj.situacao_funcional,
            },
        )
        messages.success(request, "Servidor funcional salvo com sucesso.")
        return redirect(reverse("rh:servidor_list") + _q_municipio(municipio))

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo servidor funcional",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("rh:servidor_list") + _q_municipio(municipio),
            "submit_label": "Salvar servidor",
        },
    )


@login_required
@require_perm("rh.manage")
def servidor_update(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    obj = get_object_or_404(RhCadastro, pk=pk, municipio=municipio)
    before = {
        "cargo": obj.cargo,
        "funcao": obj.funcao,
        "situacao": obj.situacao_funcional,
        "status": obj.status,
    }
    form = RhCadastroForm(request.POST or None, instance=obj, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        registrar_auditoria(
            municipio=municipio,
            modulo="RH",
            evento="SERVIDOR_FUNCIONAL_ATUALIZADO",
            entidade="RhCadastro",
            entidade_id=obj.pk,
            usuario=request.user,
            antes=before,
            depois={
                "cargo": obj.cargo,
                "funcao": obj.funcao,
                "situacao": obj.situacao_funcional,
                "status": obj.status,
            },
        )
        messages.success(request, "Servidor funcional atualizado.")
        return redirect(reverse("rh:servidor_list") + _q_municipio(municipio))

    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Editar servidor {obj.nome}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("rh:servidor_list") + _q_municipio(municipio),
            "submit_label": "Salvar alterações",
        },
    )


@login_required
@require_perm("rh.view")
def movimentacao_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    status = (request.GET.get("status") or "").strip()
    tipo = (request.GET.get("tipo") or "").strip()
    q = (request.GET.get("q") or "").strip()

    qs = RhMovimentacao.objects.filter(municipio=municipio).select_related("servidor", "aprovado_por")
    if status:
        qs = qs.filter(status=status)
    if tipo:
        qs = qs.filter(tipo=tipo)
    if q:
        qs = qs.filter(Q(servidor__nome__icontains=q) | Q(observacao__icontains=q))

    return render(
        request,
        "rh/movimentacao_list.html",
        {
            "title": "Movimentações funcionais",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-data_inicio", "-id"),
            "status": status,
            "tipo": tipo,
            "q": q,
            "status_choices": RhMovimentacao.Status.choices,
            "tipo_choices": RhMovimentacao.Tipo.choices,
            "actions": [
                {
                    "label": "Nova movimentação",
                    "url": reverse("rh:movimentacao_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Servidores",
                    "url": reverse("rh:servidor_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-users",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("rh.manage")
def movimentacao_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para registrar movimentação.")
        return redirect("rh:movimentacao_list")

    form = RhMovimentacaoForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.status = RhMovimentacao.Status.PENDENTE
        obj.save()
        registrar_auditoria(
            municipio=municipio,
            modulo="RH",
            evento="MOVIMENTACAO_CRIADA",
            entidade="RhMovimentacao",
            entidade_id=obj.pk,
            usuario=request.user,
            depois={"servidor": obj.servidor.nome, "tipo": obj.tipo, "status": obj.status},
        )
        messages.success(request, "Movimentação registrada e pendente de aprovação.")
        return redirect(reverse("rh:movimentacao_list") + _q_municipio(municipio))

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova movimentação funcional",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("rh:movimentacao_list") + _q_municipio(municipio),
            "submit_label": "Salvar movimentação",
        },
    )


def _aplicar_movimentacao(obj: RhMovimentacao):
    servidor = obj.servidor
    if obj.tipo == RhMovimentacao.Tipo.DESLIGAMENTO:
        servidor.situacao_funcional = RhCadastro.SituacaoFuncional.DESLIGADO
        servidor.status = RhCadastro.Status.INATIVO
        servidor.data_desligamento = obj.data_inicio
    elif obj.tipo == RhMovimentacao.Tipo.FERIAS:
        servidor.situacao_funcional = RhCadastro.SituacaoFuncional.FERIAS
    elif obj.tipo == RhMovimentacao.Tipo.AFASTAMENTO:
        servidor.situacao_funcional = RhCadastro.SituacaoFuncional.AFASTADO
    elif obj.tipo == RhMovimentacao.Tipo.PROGRESSAO:
        servidor.situacao_funcional = RhCadastro.SituacaoFuncional.ATIVO
    elif obj.tipo == RhMovimentacao.Tipo.LOTACAO:
        if obj.secretaria_destino_id:
            servidor.secretaria_id = obj.secretaria_destino_id
        if obj.unidade_destino_id:
            servidor.unidade_id = obj.unidade_destino_id
        if obj.setor_destino_id:
            servidor.setor_id = obj.setor_destino_id
        servidor.situacao_funcional = RhCadastro.SituacaoFuncional.ATIVO
    servidor.save()


def _decidir_movimentacao(request, pk: int, *, aprovar: bool):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(RhMovimentacao, pk=pk, municipio=municipio)
    if obj.status != RhMovimentacao.Status.PENDENTE:
        messages.warning(request, "Movimentação já foi avaliada.")
        return redirect(reverse("rh:movimentacao_list") + _q_municipio(municipio))

    obj.status = RhMovimentacao.Status.APROVADA if aprovar else RhMovimentacao.Status.RECUSADA
    obj.aprovado_por = request.user
    obj.aprovado_em = timezone.now()
    obj.save(update_fields=["status", "aprovado_por", "aprovado_em", "atualizado_em"])
    if aprovar:
        _aplicar_movimentacao(obj)
        publicar_evento_transparencia(
            municipio=municipio,
            modulo="RH",
            tipo_evento="MOVIMENTACAO_APROVADA",
            titulo=f"Movimentação funcional aprovada: {obj.get_tipo_display()}",
            descricao=obj.servidor.nome,
            referencia=str(obj.pk),
            dados={"status": obj.status, "tipo": obj.tipo},
            publico=False,
        )
    registrar_auditoria(
        municipio=municipio,
        modulo="RH",
        evento="MOVIMENTACAO_APROVADA" if aprovar else "MOVIMENTACAO_RECUSADA",
        entidade="RhMovimentacao",
        entidade_id=obj.pk,
        usuario=request.user,
        depois={"status": obj.status},
    )
    messages.success(request, "Movimentação aprovada." if aprovar else "Movimentação recusada.")
    return redirect(reverse("rh:movimentacao_list") + _q_municipio(municipio))


@login_required
@require_perm("rh.manage")
@require_POST
def movimentacao_aprovar(request, pk: int):
    return _decidir_movimentacao(request, pk, aprovar=True)


@login_required
@require_perm("rh.manage")
@require_POST
def movimentacao_recusar(request, pk: int):
    return _decidir_movimentacao(request, pk, aprovar=False)


@login_required
@require_perm("rh.view")
def documento_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    tipo = (request.GET.get("tipo") or "").strip()
    q = (request.GET.get("q") or "").strip()
    qs = RhDocumento.objects.filter(municipio=municipio).select_related("servidor")
    if tipo:
        qs = qs.filter(tipo=tipo)
    if q:
        qs = qs.filter(Q(numero__icontains=q) | Q(descricao__icontains=q) | Q(servidor__nome__icontains=q))

    return render(
        request,
        "rh/documento_list.html",
        {
            "title": "Documentos funcionais",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-data_documento", "-id"),
            "tipo": tipo,
            "q": q,
            "tipo_choices": RhDocumento.Tipo.choices,
            "actions": [
                {
                    "label": "Novo documento",
                    "url": reverse("rh:documento_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Movimentações",
                    "url": reverse("rh:movimentacao_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-right-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("rh.manage")
def documento_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para cadastrar documento.")
        return redirect("rh:documento_list")

    form = RhDocumentoForm(request.POST or None, request.FILES or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        registrar_auditoria(
            municipio=municipio,
            modulo="RH",
            evento="DOCUMENTO_FUNCIONAL_CRIADO",
            entidade="RhDocumento",
            entidade_id=obj.pk,
            usuario=request.user,
            depois={"tipo": obj.tipo, "numero": obj.numero, "servidor": obj.servidor.nome},
        )
        messages.success(request, "Documento funcional salvo com sucesso.")
        return redirect(reverse("rh:documento_list") + _q_municipio(municipio))

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo documento funcional",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("rh:documento_list") + _q_municipio(municipio),
            "submit_label": "Salvar documento",
        },
    )


# compatibilidade com rota antiga
create = servidor_create
