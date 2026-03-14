from __future__ import annotations

from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.rbac import can, scope_filter_turmas

from .models import Turma
from .models_diario import Frequencia, JustificativaFaltaPedido
from .views_diario_permissions import can_edit_diario, is_professor


def _justificativas_scope_qs(user):
    turmas_scope = scope_filter_turmas(user, Turma.objects.all())
    qs = (
        JustificativaFaltaPedido.objects.select_related(
            "aluno",
            "aula",
            "aula__diario",
            "aula__diario__turma",
            "aula__diario__professor",
            "aula__componente",
            "analisado_por",
        )
        .filter(aula__diario__turma__in=turmas_scope)
        .order_by("-criado_em", "-id")
    )
    if is_professor(user):
        qs = qs.filter(aula__diario__professor=user)
    return qs


def justificativa_falta_list_impl(request):
    status_filter = (request.GET.get("status") or "").strip().upper()
    q = (request.GET.get("q") or "").strip()

    qs = _justificativas_scope_qs(request.user)
    if status_filter in {
        JustificativaFaltaPedido.Status.PENDENTE,
        JustificativaFaltaPedido.Status.DEFERIDO,
        JustificativaFaltaPedido.Status.INDEFERIDO,
    }:
        qs = qs.filter(status=status_filter)

    if q:
        qs = qs.filter(
            Q(aluno__nome__icontains=q)
            | Q(aula__diario__turma__nome__icontains=q)
            | Q(aula__componente__nome__icontains=q)
            | Q(motivo__icontains=q)
        )

    items = list(qs[:150])
    counters = {
        "pendente": qs.filter(status=JustificativaFaltaPedido.Status.PENDENTE).count(),
        "deferido": qs.filter(status=JustificativaFaltaPedido.Status.DEFERIDO).count(),
        "indeferido": qs.filter(status=JustificativaFaltaPedido.Status.INDEFERIDO).count(),
    }
    actions = [
        {
            "label": "Meus Diários",
            "url": reverse("educacao:meus_diarios"),
            "icon": "fa-solid fa-book",
            "variant": "btn--ghost",
        },
    ]
    if can(request.user, "educacao.manage"):
        subtitle = "Painel central da secretaria para análise de justificativas por unidade/turma."
    elif is_professor(request.user):
        subtitle = "Painel do professor para análise das justificativas dos seus diários."
    else:
        subtitle = "Painel de acompanhamento das justificativas de falta."
    return render(
        request,
        "educacao/justificativa_falta_list.html",
        {
            "items": items,
            "status_filter": status_filter,
            "q": q,
            "actions": actions,
            "counters": counters,
            "subtitle": subtitle,
        },
    )


def justificativa_falta_detail_impl(request, pk: int):
    pedido = get_object_or_404(_justificativas_scope_qs(request.user), pk=pk)
    diario = pedido.aula.diario
    can_decide = can_edit_diario(request.user, diario) or can(request.user, "educacao.manage")

    if request.method == "POST":
        if not can_decide:
            return HttpResponseForbidden("403 — Você não tem permissão para decidir este pedido.")

        decisao = (request.POST.get("decisao") or "").strip().upper()
        parecer = (request.POST.get("parecer") or "").strip()
        if decisao not in {JustificativaFaltaPedido.Status.DEFERIDO, JustificativaFaltaPedido.Status.INDEFERIDO}:
            messages.error(request, "Decisão inválida.")
            return redirect(reverse("educacao:justificativa_falta_detail", args=[pedido.pk]))

        if decisao == JustificativaFaltaPedido.Status.INDEFERIDO and not parecer:
            messages.error(request, "Informe o parecer para indeferir o pedido.")
            return redirect(reverse("educacao:justificativa_falta_detail", args=[pedido.pk]))

        pedido.status = decisao
        pedido.parecer = parecer
        pedido.analisado_em = timezone.now()
        pedido.analisado_por = request.user
        pedido.save(update_fields=["status", "parecer", "analisado_em", "analisado_por", "atualizado_em"])

        if decisao == JustificativaFaltaPedido.Status.DEFERIDO:
            Frequencia.objects.update_or_create(
                aula=pedido.aula,
                aluno=pedido.aluno,
                defaults={"status": Frequencia.Status.JUSTIFICADA},
            )
            messages.success(request, "Pedido deferido e frequência atualizada para Justificada.")
        else:
            Frequencia.objects.update_or_create(
                aula=pedido.aula,
                aluno=pedido.aluno,
                defaults={"status": Frequencia.Status.FALTA},
            )
            messages.success(request, "Pedido indeferido. Frequência mantida como Falta.")

        return redirect(reverse("educacao:justificativa_falta_detail", args=[pedido.pk]))

    actions = [
        {
            "label": "Voltar",
            "url": reverse("educacao:justificativa_falta_list"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        },
    ]
    return render(
        request,
        "educacao/justificativa_falta_detail.html",
        {
            "pedido": pedido,
            "can_decide": can_decide,
            "actions": actions,
        },
    )
