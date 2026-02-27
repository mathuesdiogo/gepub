from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import require_perm
from apps.core.rbac import is_admin
from apps.org.models import Municipio

from .forms import PontoCadastroForm, PontoFechamentoCompetenciaForm, PontoOcorrenciaForm, PontoVinculoEscalaForm
from .models import PontoCadastro, PontoFechamentoCompetencia, PontoOcorrencia, PontoVinculoEscala


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


def _qs_municipio_suffix(municipio: Municipio) -> str:
    return f"?municipio={municipio.pk}"


def _competencia_bounds(competencia: str) -> tuple[date, date]:
    dt = datetime.strptime(competencia, "%Y-%m")
    first = date(dt.year, dt.month, 1)
    last = date(dt.year, dt.month, monthrange(dt.year, dt.month)[1])
    return first, last


def _recompute_competencia_totals(obj: PontoFechamentoCompetencia) -> None:
    first, last = _competencia_bounds(obj.competencia)
    ativos = (
        PontoVinculoEscala.objects.filter(
            municipio=obj.municipio,
            data_inicio__lte=last,
        )
        .filter(Q(data_fim__isnull=True) | Q(data_fim__gte=first))
        .values("servidor_id")
        .distinct()
        .count()
    )
    ocorrencias = PontoOcorrencia.objects.filter(municipio=obj.municipio, competencia=obj.competencia)
    obj.total_servidores = ativos
    obj.total_ocorrencias = ocorrencias.count()
    obj.total_pendentes = ocorrencias.filter(status=PontoOcorrencia.Status.PENDENTE).count()


@login_required
@require_perm("ponto.view")
def index(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    escalas_qs = PontoCadastro.objects.filter(municipio=municipio)
    vinculos_qs = PontoVinculoEscala.objects.filter(municipio=municipio)
    ocorrencias_qs = PontoOcorrencia.objects.filter(municipio=municipio)
    competencias_qs = PontoFechamentoCompetencia.objects.filter(municipio=municipio)

    ocorrencias_pendentes = ocorrencias_qs.filter(status=PontoOcorrencia.Status.PENDENTE)
    competencias_abertas = competencias_qs.filter(status=PontoFechamentoCompetencia.Status.ABERTA)

    return render(
        request,
        "ponto/index.html",
        {
            "title": "Ponto e Frequência",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "cards": [
                {"label": "Escalas/Turnos ativos", "value": escalas_qs.filter(status=PontoCadastro.Status.ATIVO).count()},
                {"label": "Vínculos ativos", "value": vinculos_qs.filter(ativo=True).count()},
                {"label": "Ocorrências pendentes", "value": ocorrencias_pendentes.count()},
                {"label": "Competências abertas", "value": competencias_abertas.count()},
            ],
            "latest_ocorrencias": ocorrencias_qs.select_related("servidor", "vinculo", "vinculo__escala")[:8],
            "latest_competencias": competencias_qs[:6],
            "actions": [
                {
                    "label": "Nova ocorrência",
                    "url": reverse("ponto:ocorrencia_create") + _qs_municipio_suffix(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Nova competência",
                    "url": reverse("ponto:competencia_create") + _qs_municipio_suffix(municipio),
                    "icon": "fa-solid fa-calendar-plus",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Escalas/Turnos",
                    "url": reverse("ponto:escala_list") + _qs_municipio_suffix(municipio),
                    "icon": "fa-solid fa-business-time",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Vínculos",
                    "url": reverse("ponto:vinculo_list") + _qs_municipio_suffix(municipio),
                    "icon": "fa-solid fa-users-gear",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("ponto.manage")
def escala_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para cadastrar escala.")
        return redirect("ponto:escala_list")

    form = PontoCadastroForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        messages.success(request, "Escala/turno salvo com sucesso.")
        return redirect(reverse("ponto:escala_list") + _qs_municipio_suffix(municipio))

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova escala/turno",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("ponto:escala_list") + _qs_municipio_suffix(municipio),
            "submit_label": "Salvar escala",
        },
    )


@login_required
@require_perm("ponto.manage")
def escala_update(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    obj = get_object_or_404(PontoCadastro, pk=pk, municipio=municipio)
    form = PontoCadastroForm(request.POST or None, instance=obj, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Escala atualizada com sucesso.")
        return redirect(reverse("ponto:escala_list") + _qs_municipio_suffix(municipio))

    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Editar escala {obj.codigo}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("ponto:escala_list") + _qs_municipio_suffix(municipio),
            "submit_label": "Salvar alterações",
        },
    )


@login_required
@require_perm("ponto.view")
def escala_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    turno = (request.GET.get("turno") or "").strip()

    qs = PontoCadastro.objects.filter(municipio=municipio).select_related("secretaria", "unidade", "setor")
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(nome__icontains=q) | Q(observacao__icontains=q))
    if status:
        qs = qs.filter(status=status)
    if turno:
        qs = qs.filter(tipo_turno=turno)

    return render(
        request,
        "ponto/escala_list.html",
        {
            "title": "Escalas e turnos",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("nome"),
            "q": q,
            "status": status,
            "turno": turno,
            "status_choices": PontoCadastro.Status.choices,
            "turno_choices": PontoCadastro.Turno.choices,
            "actions": [
                {
                    "label": "Nova escala",
                    "url": reverse("ponto:escala_create") + _qs_municipio_suffix(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Voltar ao painel",
                    "url": reverse("ponto:index") + _qs_municipio_suffix(municipio),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("ponto.view")
def vinculo_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    ativo = (request.GET.get("ativo") or "").strip()

    qs = PontoVinculoEscala.objects.filter(municipio=municipio).select_related("escala", "servidor", "unidade", "setor")
    if q:
        qs = qs.filter(
            Q(servidor__first_name__icontains=q)
            | Q(servidor__last_name__icontains=q)
            | Q(servidor__username__icontains=q)
            | Q(escala__nome__icontains=q)
            | Q(escala__codigo__icontains=q)
        )
    if ativo in {"0", "1"}:
        qs = qs.filter(ativo=(ativo == "1"))

    return render(
        request,
        "ponto/vinculo_list.html",
        {
            "title": "Vínculos de escala",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-ativo", "servidor__first_name", "servidor__username"),
            "q": q,
            "ativo": ativo,
            "actions": [
                {
                    "label": "Novo vínculo",
                    "url": reverse("ponto:vinculo_create") + _qs_municipio_suffix(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Escalas",
                    "url": reverse("ponto:escala_list") + _qs_municipio_suffix(municipio),
                    "icon": "fa-solid fa-business-time",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("ponto.manage")
def vinculo_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para cadastrar vínculo.")
        return redirect("ponto:vinculo_list")

    form = PontoVinculoEscalaForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        messages.success(request, "Vínculo cadastrado com sucesso.")
        return redirect(reverse("ponto:vinculo_list") + _qs_municipio_suffix(municipio))

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo vínculo de escala",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("ponto:vinculo_list") + _qs_municipio_suffix(municipio),
            "submit_label": "Salvar vínculo",
        },
    )


@login_required
@require_perm("ponto.manage")
@require_POST
def vinculo_toggle(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    obj = get_object_or_404(PontoVinculoEscala, pk=pk, municipio=municipio)
    obj.ativo = not obj.ativo
    if not obj.ativo and not obj.data_fim:
        obj.data_fim = date.today()
    if obj.ativo:
        obj.data_fim = None
    obj.save(update_fields=["ativo", "data_fim", "atualizado_em"])
    messages.success(request, "Status do vínculo atualizado.")
    return redirect(reverse("ponto:vinculo_list") + _qs_municipio_suffix(municipio))


@login_required
@require_perm("ponto.view")
def ocorrencia_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    tipo = (request.GET.get("tipo") or "").strip()
    competencia = (request.GET.get("competencia") or "").strip()

    qs = PontoOcorrencia.objects.filter(municipio=municipio).select_related("servidor", "vinculo", "vinculo__escala")
    if q:
        qs = qs.filter(
            Q(servidor__first_name__icontains=q)
            | Q(servidor__last_name__icontains=q)
            | Q(servidor__username__icontains=q)
            | Q(descricao__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)
    if tipo:
        qs = qs.filter(tipo=tipo)
    if competencia:
        qs = qs.filter(competencia=competencia)

    competencias = (
        PontoFechamentoCompetencia.objects.filter(municipio=municipio)
        .values_list("competencia", flat=True)
        .order_by("-competencia")
    )

    return render(
        request,
        "ponto/ocorrencia_list.html",
        {
            "title": "Ocorrências de ponto",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-data_ocorrencia", "-id"),
            "q": q,
            "status": status,
            "tipo": tipo,
            "competencia": competencia,
            "competencias": list(competencias),
            "status_choices": PontoOcorrencia.Status.choices,
            "tipo_choices": PontoOcorrencia.Tipo.choices,
            "actions": [
                {
                    "label": "Nova ocorrência",
                    "url": reverse("ponto:ocorrencia_create") + _qs_municipio_suffix(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Competências",
                    "url": reverse("ponto:competencia_list") + _qs_municipio_suffix(municipio),
                    "icon": "fa-solid fa-calendar-days",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("ponto.manage")
def ocorrencia_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para registrar ocorrência.")
        return redirect("ponto:ocorrencia_list")

    form = PontoOcorrenciaForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.competencia = obj.data_ocorrencia.strftime("%Y-%m")
        obj.criado_por = request.user
        obj.status = PontoOcorrencia.Status.PENDENTE
        obj.save()
        messages.success(request, "Ocorrência registrada e enviada para avaliação.")
        return redirect(reverse("ponto:ocorrencia_list") + _qs_municipio_suffix(municipio))

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova ocorrência",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("ponto:ocorrencia_list") + _qs_municipio_suffix(municipio),
            "submit_label": "Salvar ocorrência",
        },
    )


def _avalia_ocorrencia(request, pk: int, *, aprovar: bool):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    obj = get_object_or_404(PontoOcorrencia, pk=pk, municipio=municipio)
    if obj.status != PontoOcorrencia.Status.PENDENTE:
        messages.warning(request, "A ocorrência já foi avaliada.")
        return redirect(reverse("ponto:ocorrencia_list") + _qs_municipio_suffix(municipio))

    obj.status = PontoOcorrencia.Status.APROVADA if aprovar else PontoOcorrencia.Status.RECUSADA
    obj.avaliado_por = request.user
    obj.avaliado_em = timezone.now()
    obj.save(update_fields=["status", "avaliado_por", "avaliado_em", "atualizado_em"])
    messages.success(request, "Ocorrência aprovada com sucesso." if aprovar else "Ocorrência recusada com sucesso.")
    return redirect(reverse("ponto:ocorrencia_list") + _qs_municipio_suffix(municipio))


@login_required
@require_perm("ponto.manage")
@require_POST
def ocorrencia_aprovar(request, pk: int):
    return _avalia_ocorrencia(request, pk, aprovar=True)


@login_required
@require_perm("ponto.manage")
@require_POST
def ocorrencia_recusar(request, pk: int):
    return _avalia_ocorrencia(request, pk, aprovar=False)


@login_required
@require_perm("ponto.view")
def competencia_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    status = (request.GET.get("status") or "").strip()

    qs = PontoFechamentoCompetencia.objects.filter(municipio=municipio)
    if status:
        qs = qs.filter(status=status)

    return render(
        request,
        "ponto/competencia_list.html",
        {
            "title": "Fechamento por competência",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-competencia"),
            "status": status,
            "status_choices": PontoFechamentoCompetencia.Status.choices,
            "actions": [
                {
                    "label": "Nova competência",
                    "url": reverse("ponto:competencia_create") + _qs_municipio_suffix(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "Ocorrências",
                    "url": reverse("ponto:ocorrencia_list") + _qs_municipio_suffix(municipio),
                    "icon": "fa-solid fa-triangle-exclamation",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("ponto.manage")
def competencia_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para abrir competência.")
        return redirect("ponto:competencia_list")

    form = PontoFechamentoCompetenciaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.status = PontoFechamentoCompetencia.Status.ABERTA
        _recompute_competencia_totals(obj)
        try:
            obj.save()
        except IntegrityError:
            form.add_error("competencia", "Essa competência já existe para o município.")
        else:
            messages.success(request, "Competência aberta com sucesso.")
            return redirect(reverse("ponto:competencia_list") + _qs_municipio_suffix(municipio))

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Abrir competência",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("ponto:competencia_list") + _qs_municipio_suffix(municipio),
            "submit_label": "Abrir competência",
        },
    )


@login_required
@require_perm("ponto.manage")
@require_POST
def competencia_fechar(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    obj = get_object_or_404(PontoFechamentoCompetencia, pk=pk, municipio=municipio)
    if obj.status == PontoFechamentoCompetencia.Status.FECHADA:
        messages.info(request, "A competência já está fechada.")
        return redirect(reverse("ponto:competencia_list") + _qs_municipio_suffix(municipio))

    _recompute_competencia_totals(obj)
    obj.status = PontoFechamentoCompetencia.Status.FECHADA
    obj.fechado_por = request.user
    obj.fechado_em = timezone.now()
    obj.save(
        update_fields=[
            "status",
            "total_servidores",
            "total_ocorrencias",
            "total_pendentes",
            "fechado_por",
            "fechado_em",
            "atualizado_em",
        ]
    )
    if obj.total_pendentes:
        messages.warning(request, f"Competência fechada com {obj.total_pendentes} ocorrências pendentes.")
    else:
        messages.success(request, "Competência fechada com sucesso.")
    return redirect(reverse("ponto:competencia_list") + _qs_municipio_suffix(municipio))


@login_required
@require_perm("ponto.manage")
@require_POST
def competencia_reabrir(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    obj = get_object_or_404(PontoFechamentoCompetencia, pk=pk, municipio=municipio)
    if obj.status == PontoFechamentoCompetencia.Status.ABERTA:
        messages.info(request, "A competência já está aberta.")
        return redirect(reverse("ponto:competencia_list") + _qs_municipio_suffix(municipio))

    obj.status = PontoFechamentoCompetencia.Status.ABERTA
    obj.fechado_por = None
    obj.fechado_em = None
    _recompute_competencia_totals(obj)
    obj.save(
        update_fields=[
            "status",
            "fechado_por",
            "fechado_em",
            "total_servidores",
            "total_ocorrencias",
            "total_pendentes",
            "atualizado_em",
        ]
    )
    messages.success(request, "Competência reaberta com sucesso.")
    return redirect(reverse("ponto:competencia_list") + _qs_municipio_suffix(municipio))


# compatibilidade com rota antiga `ponto:create`
create = escala_create
