from django.contrib import messages
from django.contrib.auth.decorators import login_required
from datetime import datetime, time
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.decorators import require_perm
from apps.core.models import DocumentoEmitido
from apps.core.rbac import can, scope_filter_unidades
from apps.org.models import Unidade

from .forms import (
    AlergiaSaudeForm,
    AnexoAtendimentoSaudeForm,
    EvolucaoClinicaSaudeForm,
    ExamePedidoSaudeForm,
    ExameResultadoSaudeForm,
    PrescricaoItemSaudeForm,
    PrescricaoSaudeForm,
    ProblemaAtivoSaudeForm,
    TriagemSaudeForm,
)
from .models import (
    AlergiaSaude,
    AnexoAtendimentoSaude,
    AtendimentoSaude,
    AuditoriaAcessoProntuarioSaude,
    AuditoriaAlteracaoSaude,
    DocumentoClinicoSaude,
    EvolucaoClinicaSaude,
    ExamePedidoSaude,
    ExameResultadoSaude,
    PrescricaoItemSaude,
    PrescricaoSaude,
    ProblemaAtivoSaude,
    TriagemSaude,
)


def _atendimento_scoped(request, pk: int):
    unidades_qs = scope_filter_unidades(request.user, Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE))
    qs = AtendimentoSaude.objects.select_related("unidade", "profissional", "aluno").filter(
        unidade_id__in=unidades_qs.values_list("id", flat=True)
    )
    return get_object_or_404(qs, pk=pk)


def _log_model_changes(model_label: str, instance, cleaned_data: dict, user, justificativa: str):
    for field, new_value in cleaned_data.items():
        if not hasattr(instance, field):
            continue
        old_value = getattr(instance, field)
        if old_value != new_value:
            AuditoriaAlteracaoSaude.objects.create(
                entidade=model_label,
                objeto_id=str(instance.pk),
                campo=field,
                valor_anterior="" if old_value is None else str(old_value),
                valor_novo="" if new_value is None else str(new_value),
                justificativa=justificativa,
                alterado_por=user,
            )


def _is_outside_edit_window(atendimento) -> bool:
    window_hours = int(getattr(settings, "SAUDE_EDIT_WINDOW_HOURS", 24) or 24)
    atendimento_dt = timezone.make_aware(datetime.combine(atendimento.data, time.min))
    delta = timezone.now() - atendimento_dt
    return delta.total_seconds() > (window_hours * 3600)


@login_required
@require_perm("saude.view")
def prontuario_hub(request, pk: int):
    atendimento = _atendimento_scoped(request, pk)
    is_outside_window = _is_outside_edit_window(atendimento)

    AuditoriaAcessoProntuarioSaude.objects.create(
        usuario=request.user,
        atendimento=atendimento,
        aluno=atendimento.aluno if atendimento.aluno_id else None,
        acao="PRONTUARIO_HUB_VIEW",
        ip=request.META.get("REMOTE_ADDR", ""),
    )

    triagem_obj = TriagemSaude.objects.filter(atendimento=atendimento).first()
    evolucoes = atendimento.evolucoes_clinicas.select_related("autor").all()[:20]
    anexos = atendimento.anexos_clinicos.select_related("criado_por").all()[:20]
    prescricoes = atendimento.prescricoes.prefetch_related("itens").all()[:10]
    exames = atendimento.exames_pedidos.select_related("resultado").all()[:20]

    problemas = []
    alergias = []
    if atendimento.aluno_id:
        problemas = list(ProblemaAtivoSaude.objects.filter(aluno=atendimento.aluno).order_by("-criado_em")[:20])
        alergias = list(AlergiaSaude.objects.filter(aluno=atendimento.aluno).order_by("agente")[:20])

    if request.method == "POST":
        if not can(request.user, "saude.manage"):
            messages.error(request, "Você não tem permissão para alterar dados clínicos.")
            return redirect("saude:prontuario_hub", pk=atendimento.pk)

        action = (request.POST.get("_action") or "").strip()

        if action == "save_triagem":
            form = TriagemSaudeForm(request.POST, instance=triagem_obj)
            if form.is_valid():
                justificativa = (request.POST.get("justificativa_alteracao") or "").strip()
                if triagem_obj and form.has_changed() and is_outside_window and not request.user.is_superuser:
                    messages.error(request, "Janela de edição clínica expirada para esta triagem.")
                    return redirect("saude:prontuario_hub", pk=atendimento.pk)
                if triagem_obj and form.has_changed() and not justificativa:
                    messages.error(request, "Informe justificativa para alterar uma triagem já registrada.")
                    return redirect("saude:prontuario_hub", pk=atendimento.pk)
                triagem = form.save(commit=False)
                triagem.atendimento = atendimento
                triagem.save()
                if triagem_obj and form.has_changed():
                    _log_model_changes("TriagemSaude", triagem, form.cleaned_data, request.user, justificativa)
                messages.success(request, "Triagem salva com sucesso.")
                return redirect("saude:prontuario_hub", pk=atendimento.pk)
            messages.error(request, "Corrija os erros da triagem.")

        elif action == "add_evolucao":
            form = EvolucaoClinicaSaudeForm(request.POST)
            if form.is_valid():
                ev = form.save(commit=False)
                ev.atendimento = atendimento
                ev.autor = request.user
                ev.save()
                messages.success(request, "Evolução registrada.")
                return redirect("saude:prontuario_hub", pk=atendimento.pk)
            messages.error(request, "Corrija os erros da evolução.")

        elif action == "add_problema" and atendimento.aluno_id:
            form = ProblemaAtivoSaudeForm(request.POST)
            if form.is_valid():
                p = form.save(commit=False)
                p.aluno = atendimento.aluno
                p.save()
                messages.success(request, "Problema ativo registrado.")
                return redirect("saude:prontuario_hub", pk=atendimento.pk)
            messages.error(request, "Corrija os erros do problema ativo.")

        elif action == "add_alergia" and atendimento.aluno_id:
            form = AlergiaSaudeForm(request.POST)
            if form.is_valid():
                a = form.save(commit=False)
                a.aluno = atendimento.aluno
                a.save()
                messages.success(request, "Alergia registrada.")
                return redirect("saude:prontuario_hub", pk=atendimento.pk)
            messages.error(request, "Corrija os erros da alergia.")

        elif action == "add_anexo":
            form = AnexoAtendimentoSaudeForm(request.POST, request.FILES)
            if form.is_valid():
                an = form.save(commit=False)
                an.atendimento = atendimento
                an.criado_por = request.user
                an.save()
                messages.success(request, "Anexo adicionado.")
                return redirect("saude:prontuario_hub", pk=atendimento.pk)
            messages.error(request, "Corrija os erros do anexo.")

        elif action == "add_prescricao":
            p_form = PrescricaoSaudeForm(request.POST)
            i_form = PrescricaoItemSaudeForm(request.POST, prefix="item")
            if p_form.is_valid() and i_form.is_valid():
                last = atendimento.prescricoes.order_by("-versao").first()
                versao = (last.versao + 1) if last else 1
                prescricao = p_form.save(commit=False)
                prescricao.atendimento = atendimento
                prescricao.versao = versao
                prescricao.criado_por = request.user
                prescricao.save()

                item = i_form.save(commit=False)
                item.prescricao = prescricao
                item.save()

                # Integração com documento emitido (receita)
                documento_emitido = DocumentoEmitido.objects.create(
                    tipo="SAUDE.RECEITA",
                    titulo=f"Receita {atendimento.paciente_nome} v{versao}",
                    gerado_por=request.user,
                    origem_url=reverse("saude:prontuario_hub", args=[atendimento.pk]),
                )
                DocumentoClinicoSaude.objects.create(
                    atendimento=atendimento,
                    tipo=DocumentoClinicoSaude.Tipo.RECEITA,
                    titulo=f"Receita v{versao}",
                    conteudo=item.orientacoes or f"{item.medicamento} - {item.dose}",
                    documento_emitido=documento_emitido,
                    criado_por=request.user,
                )

                messages.success(request, "Prescrição registrada com sucesso.")
                return redirect("saude:prontuario_hub", pk=atendimento.pk)
            messages.error(request, "Corrija os erros da prescrição.")

        elif action == "add_exame":
            form = ExamePedidoSaudeForm(request.POST)
            if form.is_valid():
                ex = form.save(commit=False)
                ex.atendimento = atendimento
                ex.criado_por = request.user
                ex.save()
                messages.success(request, "Pedido de exame registrado.")
                return redirect("saude:prontuario_hub", pk=atendimento.pk)
            messages.error(request, "Corrija os erros do pedido de exame.")

        elif action == "save_resultado":
            pedido_id = request.POST.get("pedido_id")
            pedido = ExamePedidoSaude.objects.filter(pk=pedido_id, atendimento=atendimento).first()
            if pedido:
                instance = ExameResultadoSaude.objects.filter(pedido=pedido).first()
                form = ExameResultadoSaudeForm(request.POST, request.FILES, instance=instance, prefix=f"res_{pedido.id}")
                if form.is_valid():
                    justificativa = (request.POST.get("justificativa_alteracao") or "").strip()
                    if instance and form.has_changed() and is_outside_window and not request.user.is_superuser:
                        messages.error(request, "Janela de edição clínica expirada para este resultado.")
                        return redirect("saude:prontuario_hub", pk=atendimento.pk)
                    if instance and form.has_changed() and not justificativa:
                        messages.error(request, "Informe justificativa para alterar um resultado já registrado.")
                        return redirect("saude:prontuario_hub", pk=atendimento.pk)
                    res = form.save(commit=False)
                    res.pedido = pedido
                    res.criado_por = request.user
                    res.save()
                    if instance and form.has_changed():
                        _log_model_changes("ExameResultadoSaude", res, form.cleaned_data, request.user, justificativa)
                    pedido.status = ExamePedidoSaude.Status.RESULTADO
                    pedido.save(update_fields=["status"])
                    messages.success(request, "Resultado do exame salvo.")
                    return redirect("saude:prontuario_hub", pk=atendimento.pk)
            messages.error(request, "Não foi possível salvar o resultado do exame.")

    triagem_form = TriagemSaudeForm(instance=triagem_obj)
    evolucao_form = EvolucaoClinicaSaudeForm()
    problema_form = ProblemaAtivoSaudeForm()
    alergia_form = AlergiaSaudeForm()
    anexo_form = AnexoAtendimentoSaudeForm()
    prescricao_form = PrescricaoSaudeForm()
    prescricao_item_form = PrescricaoItemSaudeForm(prefix="item")
    exame_form = ExamePedidoSaudeForm()

    exame_blocos = []
    for pedido in exames:
        inst = ExameResultadoSaude.objects.filter(pedido=pedido).first()
        exame_blocos.append(
            {
                "pedido": pedido,
                "form_resultado": ExameResultadoSaudeForm(instance=inst, prefix=f"res_{pedido.id}"),
            }
        )

    actions = [
        {
            "label": "Voltar",
            "url": reverse("saude:atendimento_detail", args=[atendimento.pk]),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }
    ]

    return render(
        request,
        "saude/prontuario_hub.html",
        {
            "atendimento": atendimento,
            "actions": actions,
            "triagem_form": triagem_form,
            "evolucao_form": evolucao_form,
            "problema_form": problema_form,
            "alergia_form": alergia_form,
            "anexo_form": anexo_form,
            "prescricao_form": prescricao_form,
            "prescricao_item_form": prescricao_item_form,
            "exame_form": exame_form,
            "evolucoes": evolucoes,
            "problemas": problemas,
            "alergias": alergias,
            "anexos": anexos,
            "prescricoes": prescricoes,
            "exame_blocos": exame_blocos,
            "is_outside_edit_window": is_outside_window and not request.user.is_superuser,
            "edit_window_hours": int(getattr(settings, "SAUDE_EDIT_WINDOW_HOURS", 24) or 24),
        },
    )
