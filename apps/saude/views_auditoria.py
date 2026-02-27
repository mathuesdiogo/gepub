from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import scope_filter_unidades
from apps.org.models import Unidade

from .models import AuditoriaAcessoProntuarioSaude


@login_required
@require_perm("saude.view")
def auditoria_prontuario_list(request):
    q = (request.GET.get("q") or "").strip()
    acao = (request.GET.get("acao") or "").strip()

    unidades_qs = scope_filter_unidades(
        request.user,
        Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE).order_by("nome"),
    )

    qs = AuditoriaAcessoProntuarioSaude.objects.select_related("usuario", "atendimento", "aluno").filter(
        Q(atendimento__unidade_id__in=unidades_qs.values_list("id", flat=True))
        | Q(atendimento__isnull=True, aluno__isnull=False)
    )

    if q:
        qs = qs.filter(
            Q(usuario__username__icontains=q)
            | Q(acao__icontains=q)
            | Q(atendimento__paciente_nome__icontains=q)
            | Q(aluno__nome__icontains=q)
        )
    if acao:
        qs = qs.filter(acao=acao)

    page_obj = Paginator(qs.order_by("-criado_em", "-id"), 15).get_page(request.GET.get("page"))

    headers = [
        {"label": "Data/Hora", "width": "170px"},
        {"label": "Usuário"},
        {"label": "Paciente"},
        {"label": "Ação", "width": "220px"},
        {"label": "IP", "width": "130px"},
    ]
    rows = []
    for item in page_obj:
        paciente = "—"
        url = ""
        if item.atendimento_id:
            paciente = item.atendimento.paciente_nome
            url = reverse("saude:prontuario_hub", args=[item.atendimento_id])
        elif item.aluno_id:
            paciente = item.aluno.nome

        rows.append(
            {
                "cells": [
                    {"text": item.criado_em.strftime("%d/%m/%Y %H:%M")},
                    {"text": item.usuario.get_username()},
                    {"text": paciente, "url": url} if url else {"text": paciente},
                    {"text": item.acao},
                    {"text": item.ip or "—"},
                ],
            }
        )

    action_options = sorted(AuditoriaAcessoProntuarioSaude.objects.values_list("acao", flat=True).distinct())
    extra_filters = """
      <div class=\"filter-bar__field\">
        <label class=\"small\">Ação</label>
        <select name=\"acao\">
          <option value=\"\">Todas</option>
    """
    for value in action_options:
        selected = "selected" if acao == value else ""
        extra_filters += f"<option value=\"{value}\" {selected}>{value}</option>"
    extra_filters += """
        </select>
      </div>
    """

    return render(
        request,
        "saude/auditoria_prontuario_list.html",
        {
            "q": q,
            "acao": acao,
            "page_obj": page_obj,
            "headers": headers,
            "rows": rows,
            "actions": [],
            "action_url": reverse("saude:auditoria_prontuario_list"),
            "clear_url": reverse("saude:auditoria_prontuario_list"),
            "has_filters": bool(acao),
            "extra_filters": extra_filters,
        },
    )
