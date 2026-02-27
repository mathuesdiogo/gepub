from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.models import DocumentoEmitido
from apps.core.rbac import can, scope_filter_unidades
from apps.org.models import Unidade

from .forms import DocumentoClinicoSaudeForm
from .models import AtendimentoSaude, DocumentoClinicoSaude


def _scoped_atendimento_qs(user):
    unidades_qs = scope_filter_unidades(user, Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE))
    return AtendimentoSaude.objects.select_related("unidade", "profissional").filter(
        unidade_id__in=unidades_qs.values_list("id", flat=True)
    )


@login_required
@require_perm("saude.view")
def documento_list(request, atendimento_id: int):
    atendimento = get_object_or_404(_scoped_atendimento_qs(request.user), pk=atendimento_id)
    docs = atendimento.documentos_clinicos.select_related("documento_emitido", "criado_por").all()

    actions = [
        {
            "label": "Voltar",
            "url": reverse("saude:atendimento_detail", args=[atendimento.pk]),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }
    ]
    if can(request.user, "saude.manage"):
        actions.append(
            {
                "label": "Novo Documento",
                "url": reverse("saude:documento_create", args=[atendimento.pk]),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            }
        )

    headers = [
        {"label": "Tipo", "width": "160px"},
        {"label": "Título"},
        {"label": "Emitido em", "width": "170px"},
        {"label": "Validação", "width": "220px"},
    ]
    rows = []
    for d in docs:
        valid_url = "—"
        if d.documento_emitido_id:
            valid_url = reverse("core:guia_telas") + f"?q={d.documento_emitido.codigo}"
        rows.append(
            {
                "cells": [
                    {"text": d.get_tipo_display(), "url": reverse("saude:documento_detail", args=[d.pk])},
                    {"text": d.titulo, "url": reverse("saude:documento_detail", args=[d.pk])},
                    {"text": d.criado_em.strftime("%d/%m/%Y %H:%M")},
                    {"text": "Abrir registro" if d.documento_emitido_id else "—", "url": valid_url if d.documento_emitido_id else ""},
                ],
                "can_edit": False,
                "edit_url": "",
            }
        )

    return render(
        request,
        "saude/documento_list.html",
        {
            "atendimento": atendimento,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "page_obj": None,
        },
    )


@login_required
@require_perm("saude.manage")
def documento_create(request, atendimento_id: int):
    atendimento = get_object_or_404(_scoped_atendimento_qs(request.user), pk=atendimento_id)

    if request.method == "POST":
        form = DocumentoClinicoSaudeForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.atendimento = atendimento
            obj.criado_por = request.user

            documento_emitido = DocumentoEmitido.objects.create(
                tipo=f"SAUDE.{obj.tipo}",
                titulo=obj.titulo,
                gerado_por=request.user,
                origem_url=reverse("saude:documento_detail", args=[0]),
            )
            obj.documento_emitido = documento_emitido
            obj.save()

            # Atualiza com a URL real após save
            documento_emitido.origem_url = reverse("saude:documento_detail", args=[obj.pk])
            documento_emitido.save(update_fields=["origem_url"])

            messages.success(request, "Documento clínico emitido com sucesso.")
            return redirect("saude:documento_detail", obj.pk)

        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = DocumentoClinicoSaudeForm()

    return render(
        request,
        "saude/documento_form.html",
        {
            "form": form,
            "atendimento": atendimento,
            "mode": "create",
            "cancel_url": reverse("saude:documento_list", args=[atendimento.pk]),
            "submit_label": "Emitir documento",
            "action_url": reverse("saude:documento_create", args=[atendimento.pk]),
        },
    )


@login_required
@require_perm("saude.view")
def documento_detail(request, pk: int):
    obj = get_object_or_404(
        DocumentoClinicoSaude.objects.select_related("atendimento", "atendimento__unidade", "documento_emitido", "criado_por"),
        pk=pk,
    )

    # escopo de segurança por unidade
    unidades_qs = scope_filter_unidades(request.user, Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE))
    if not unidades_qs.filter(pk=obj.atendimento.unidade_id).exists():
        return redirect("saude:index")

    actions = [
        {
            "label": "Voltar",
            "url": reverse("saude:documento_list", args=[obj.atendimento_id]),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }
    ]

    fields = [
        {"label": "Tipo", "value": obj.get_tipo_display()},
        {"label": "Título", "value": obj.titulo},
        {"label": "Paciente", "value": obj.atendimento.paciente_nome},
        {"label": "Profissional", "value": obj.atendimento.profissional.nome},
        {"label": "Unidade", "value": obj.atendimento.unidade.nome},
        {"label": "Gerado por", "value": getattr(obj.criado_por, "username", "—")},
        {"label": "Conteúdo", "value": obj.conteudo},
    ]

    pills = []
    if obj.documento_emitido_id:
        pills.append({"label": "Código", "value": str(obj.documento_emitido.codigo), "variant": "info"})

    return render(request, "saude/documento_detail.html", {"obj": obj, "fields": fields, "pills": pills, "actions": actions})
