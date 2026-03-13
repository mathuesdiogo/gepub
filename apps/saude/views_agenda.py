from datetime import datetime, time, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from apps.comunicacao.services import queue_event_notifications
from apps.core.decorators import require_perm
from apps.core.rbac import can, scope_filter_unidades
from apps.org.models import Unidade

from .forms import AgendamentoSaudeForm
from .models import AgendamentoSaude, BloqueioAgendaSaude, ProfissionalSaude


def _scoped_unidades(user):
    return scope_filter_unidades(user, Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE).order_by("nome"))


def _scoped_profissionais(unidades_qs):
    return ProfissionalSaude.objects.filter(unidade_id__in=unidades_qs.values_list("id", flat=True), ativo=True).order_by("nome")


def _has_slot_conflict(*, unidade_id: int, profissional_id: int, sala_id: int | None, inicio, fim, ignore_agendamento_id: int | None = None) -> bool:
    agendamentos = AgendamentoSaude.objects.filter(
        unidade_id=unidade_id,
        inicio__lt=fim,
        fim__gt=inicio,
    ).exclude(status=AgendamentoSaude.Status.CANCELADO)
    if ignore_agendamento_id:
        agendamentos = agendamentos.exclude(pk=ignore_agendamento_id)
    agendamento_conflict = agendamentos.filter(profissional_id=profissional_id).exists()
    if not agendamento_conflict and sala_id:
        agendamento_conflict = agendamentos.filter(sala_id=sala_id).exists()
    if agendamento_conflict:
        return True

    bloqueios = BloqueioAgendaSaude.objects.filter(
        unidade_id=unidade_id,
        inicio__lt=fim,
        fim__gt=inicio,
    )
    bloqueio_conflict = bloqueios.filter(
        Q(profissional_id=profissional_id) | Q(profissional__isnull=True)
    ).filter(
        (Q(sala_id=sala_id) if sala_id else Q(sala__isnull=True)) | Q(sala__isnull=True)
    ).exists()
    return bloqueio_conflict


def _find_next_available_slot(agendamento: AgendamentoSaude, *, max_days: int = 21):
    duration = agendamento.fim - agendamento.inicio
    if duration.total_seconds() <= 0:
        duration = timedelta(minutes=30)

    original_start_local = timezone.localtime(agendamento.inicio)
    base_date = timezone.localdate() + timedelta(days=1)
    for delta_day in range(max(1, int(max_days))):
        candidate_date = base_date + timedelta(days=delta_day)
        candidate_start_naive = datetime.combine(candidate_date, original_start_local.timetz().replace(tzinfo=None))
        candidate_start = timezone.make_aware(candidate_start_naive)
        candidate_end = candidate_start + duration

        if _has_slot_conflict(
            unidade_id=agendamento.unidade_id,
            profissional_id=agendamento.profissional_id,
            sala_id=agendamento.sala_id,
            inicio=candidate_start,
            fim=candidate_end,
            ignore_agendamento_id=agendamento.pk,
        ):
            continue
        return candidate_start, candidate_end
    return None


@login_required
@require_perm("saude.view")
def agenda_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()

    unidades_qs = _scoped_unidades(request.user)
    base_qs = AgendamentoSaude.objects.select_related("unidade", "profissional", "especialidade", "sala").filter(
        unidade_id__in=unidades_qs.values_list("id", flat=True)
    )
    qs = base_qs

    if q:
        qs = qs.filter(
            Q(paciente_nome__icontains=q)
            | Q(paciente_cpf__icontains=q)
            | Q(profissional__nome__icontains=q)
            | Q(unidade__nome__icontains=q)
        )

    if status:
        qs = qs.filter(status=status)

    qs = qs.order_by("-inicio", "-id")
    metrics = {
        "total": base_qs.count(),
        "pendentes": base_qs.filter(status__in=[AgendamentoSaude.Status.MARCADO, AgendamentoSaude.Status.CONFIRMADO]).count(),
        "faltas": base_qs.filter(status=AgendamentoSaude.Status.FALTA).count(),
        "atendidos": base_qs.filter(status=AgendamentoSaude.Status.ATENDIDO).count(),
    }

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    can_manage = can(request.user, "saude.manage")

    actions = []
    if can_manage:
        actions.append({"label": "Novo Agendamento", "url": reverse("saude:agenda_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})

    headers = [
        {"label": "Paciente"},
        {"label": "Início", "width": "170px"},
        {"label": "Profissional"},
        {"label": "Unidade"},
        {"label": "Status", "width": "150px"},
    ]

    rows = []
    for a in page_obj:
        rows.append(
            {
                "cells": [
                    {"text": a.paciente_nome, "url": reverse("saude:agenda_detail", args=[a.pk])},
                    {"text": a.inicio.strftime("%d/%m/%Y %H:%M")},
                    {"text": getattr(a.profissional, "nome", "—")},
                    {"text": getattr(a.unidade, "nome", "—")},
                    {"text": a.get_status_display()},
                ],
                "can_edit": bool(can_manage),
                "edit_url": reverse("saude:agenda_update", args=[a.pk]) if can_manage else "",
            }
        )

    status_options = format_html_join(
        "",
        '<option value="{}"{}>{}</option>',
        ((k, " selected" if status == k else "", v) for k, v in AgendamentoSaude.Status.choices),
    )
    extra_filters = str(
        format_html(
            (
                '<div class="filter-bar__field"><label class="small">Status</label><select name="status">'
                '<option value="">Todos</option>{}</select></div>'
            ),
            status_options,
        )
    )

    return render(
        request,
        "saude/agenda_list.html",
        {
            "q": q,
            "status": status,
            "metrics": metrics,
            "page_obj": page_obj,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "action_url": reverse("saude:agenda_list"),
            "clear_url": reverse("saude:agenda_list"),
            "has_filters": bool(status),
            "extra_filters": extra_filters,
        },
    )


@login_required
@require_perm("saude.manage")
def agenda_remarcacao_auto(request):
    if request.method != "POST":
        return redirect("saude:agenda_list")

    unidades_qs = _scoped_unidades(request.user)
    dias_busca_raw = (request.POST.get("dias_busca") or "").strip()
    limite_raw = (request.POST.get("limite") or "").strip()
    try:
        dias_busca = max(1, min(90, int(dias_busca_raw or 30)))
    except Exception:
        dias_busca = 30
    try:
        limite = max(1, min(200, int(limite_raw or 30)))
    except Exception:
        limite = 30

    inicio_janela = timezone.now() - timedelta(days=dias_busca)
    faltas_qs = (
        AgendamentoSaude.objects.select_related("unidade", "profissional", "especialidade", "aluno")
        .filter(
            unidade_id__in=unidades_qs.values_list("id", flat=True),
            status=AgendamentoSaude.Status.FALTA,
            inicio__gte=inicio_janela,
        )
        .order_by("inicio", "id")[:limite]
    )

    remarcados = 0
    sem_slot = 0
    notificacoes = 0

    for item in faltas_qs:
        max_days = int(getattr(settings, "SAUDE_REMARCACAO_MAX_DIAS", 21) or 21)
        next_slot = _find_next_available_slot(item, max_days=max_days)
        if not next_slot:
            sem_slot += 1
            continue

        novo_inicio, novo_fim = next_slot
        item.inicio = novo_inicio
        item.fim = novo_fim
        item.status = AgendamentoSaude.Status.MARCADO
        item.motivo = (item.motivo or "").strip()
        item.motivo += (
            ("\n" if item.motivo else "")
            + f"Remarcação automática em {timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')}"
        )
        item.save(update_fields=["inicio", "fim", "status", "motivo"])
        remarcados += 1

        contato = ""
        if item.aluno_id and getattr(item.aluno, "telefone", ""):
            contato = (item.aluno.telefone or "").strip()
        if item.paciente_nome:
            recipients = [
                {
                    "nome": item.paciente_nome,
                    "telefone": contato,
                    "whatsapp": contato,
                    "channels": ["WHATSAPP", "SMS"],
                }
            ]
            jobs = queue_event_notifications(
                municipio=item.unidade.secretaria.municipio,
                secretaria=item.unidade.secretaria,
                unidade=item.unidade,
                event_key="saude.agendamento.remarcado",
                payload={
                    "nome": item.paciente_nome,
                    "data": timezone.localtime(item.inicio).strftime("%d/%m/%Y"),
                    "hora": timezone.localtime(item.inicio).strftime("%H:%M"),
                    "unidade": item.unidade.nome,
                    "profissional": item.profissional.nome,
                },
                recipients=recipients,
                actor=request.user,
                entity_module="SAUDE",
                entity_type="AgendamentoSaude",
                entity_id=str(item.pk),
            )
            notificacoes += len(jobs)

    if remarcados:
        messages.success(
            request,
            f"Remarcação automática concluída. Remarcados: {remarcados}, sem slot: {sem_slot}, notificações enfileiradas: {notificacoes}.",
        )
    else:
        messages.warning(request, f"Nenhum agendamento foi remarcado. Sem slot: {sem_slot}.")

    return redirect("saude:agenda_list")


@login_required
@require_perm("saude.manage")
def agenda_create(request):
    unidades_qs = _scoped_unidades(request.user)
    profissionais_qs = _scoped_profissionais(unidades_qs)

    if request.method == "POST":
        form = AgendamentoSaudeForm(request.POST, unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)
        if form.is_valid():
            obj = form.save(commit=False)

            if not unidades_qs.filter(pk=obj.unidade_id).exists():
                messages.error(request, "Unidade fora do seu escopo.")
                return redirect("saude:agenda_create")

            if not profissionais_qs.filter(pk=obj.profissional_id).exists():
                messages.error(request, "Profissional fora do seu escopo.")
                return redirect("saude:agenda_create")

            if obj.profissional.unidade_id != obj.unidade_id:
                messages.error(request, "O profissional selecionado não pertence à unidade escolhida.")
                return redirect("saude:agenda_create")

            obj.save()
            messages.success(request, "Agendamento criado com sucesso.")
            return redirect("saude:agenda_detail", obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AgendamentoSaudeForm(unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)

    return render(
        request,
        "saude/agenda_form.html",
        {
            "form": form,
            "mode": "create",
            "cancel_url": reverse("saude:agenda_list"),
            "submit_label": "Salvar",
            "action_url": reverse("saude:agenda_create"),
        },
    )


@login_required
@require_perm("saude.manage")
def agenda_update(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    profissionais_qs = _scoped_profissionais(unidades_qs)

    qs = AgendamentoSaude.objects.select_related("unidade", "profissional").filter(
        unidade_id__in=unidades_qs.values_list("id", flat=True)
    )
    obj = get_object_or_404(qs, pk=pk)

    if request.method == "POST":
        form = AgendamentoSaudeForm(request.POST, instance=obj, unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)
        if form.is_valid():
            obj2 = form.save(commit=False)

            if not unidades_qs.filter(pk=obj2.unidade_id).exists():
                messages.error(request, "Unidade fora do seu escopo.")
                return redirect("saude:agenda_update", pk=obj.pk)

            if not profissionais_qs.filter(pk=obj2.profissional_id).exists():
                messages.error(request, "Profissional fora do seu escopo.")
                return redirect("saude:agenda_update", pk=obj.pk)

            if obj2.profissional.unidade_id != obj2.unidade_id:
                messages.error(request, "O profissional selecionado não pertence à unidade escolhida.")
                return redirect("saude:agenda_update", pk=obj.pk)

            obj2.save()
            messages.success(request, "Agendamento atualizado com sucesso.")
            return redirect("saude:agenda_detail", obj2.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AgendamentoSaudeForm(instance=obj, unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)

    return render(
        request,
        "saude/agenda_form.html",
        {
            "form": form,
            "mode": "update",
            "obj": obj,
            "cancel_url": reverse("saude:agenda_detail", args=[obj.pk]),
            "submit_label": "Salvar",
            "action_url": reverse("saude:agenda_update", args=[obj.pk]),
        },
    )


@login_required
@require_perm("saude.view")
def agenda_detail(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    qs = AgendamentoSaude.objects.select_related("unidade", "profissional", "especialidade", "sala", "aluno").filter(
        unidade_id__in=unidades_qs.values_list("id", flat=True)
    )
    obj = get_object_or_404(qs, pk=pk)

    can_manage = can(request.user, "saude.manage")
    actions = [{"label": "Voltar", "url": reverse("saude:agenda_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if can_manage:
        actions.append({"label": "Editar", "url": reverse("saude:agenda_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})

    fields = [
        {"label": "Paciente", "value": obj.paciente_nome},
        {"label": "Aluno vinculado", "value": getattr(obj.aluno, "nome", "—") if obj.aluno_id else "—"},
        {"label": "Profissional", "value": getattr(obj.profissional, "nome", "—")},
        {"label": "Unidade", "value": getattr(obj.unidade, "nome", "—")},
        {"label": "Especialidade", "value": getattr(obj.especialidade, "nome", "—") if obj.especialidade_id else "—"},
        {"label": "Sala", "value": getattr(obj.sala, "nome", "—") if obj.sala_id else "—"},
        {"label": "Início", "value": obj.inicio.strftime("%d/%m/%Y %H:%M")},
        {"label": "Fim", "value": obj.fim.strftime("%d/%m/%Y %H:%M")},
        {"label": "Motivo", "value": obj.motivo or "—"},
    ]
    pills = [{"label": "Status", "value": obj.get_status_display(), "variant": "info"}]

    return render(request, "saude/agenda_detail.html", {"obj": obj, "fields": fields, "pills": pills, "actions": actions})
