from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.billing.services import MetricaLimite, verificar_limite_municipio
from apps.core.rbac import scope_filter_alunos
from apps.processos.models import ProcessoAdministrativo, ProcessoAndamento

from .forms import AlunoCreateComTurmaForm, AlunoForm
from .models import Aluno, Matricula, MatriculaMovimentacao
from .services_matricula import registrar_movimentacao
from .services_requisitos import avaliar_requisitos_matricula


def aluno_create(request):
    if request.method == "POST":
        form = AlunoCreateComTurmaForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                turma = form.cleaned_data["turma"]
                municipio = getattr(getattr(getattr(turma, "unidade", None), "secretaria", None), "municipio", None)
                if municipio:
                    limite = verificar_limite_municipio(
                        municipio,
                        MetricaLimite.ALUNOS,
                        incremento=1,
                    )
                    if not limite.permitido:
                        upgrade_url = reverse("billing:solicitar_upgrade")
                        upgrade_url += f"?municipio={municipio.pk}&tipo=ALUNOS&qtd={limite.excedente}"
                        messages.error(
                            request,
                            (
                                f"Limite de alunos excedido ({limite.atual}/{limite.limite}). "
                                f"Solicite upgrade em: {upgrade_url}"
                            ),
                        )
                        return redirect("educacao:aluno_list")
                aluno = form.save()
                avaliacao_requisitos = avaliar_requisitos_matricula(aluno=aluno, turma=turma)
                if avaliacao_requisitos.bloqueado:
                    for pendencia in avaliacao_requisitos.pendencias:
                        messages.error(request, pendencia)
                    transaction.set_rollback(True)
                    return redirect("educacao:aluno_list")
                for aviso in avaliacao_requisitos.avisos:
                    messages.warning(request, aviso)
                matricula = Matricula.objects.create(
                    aluno=aluno,
                    turma=turma,
                    data_matricula=timezone.localdate(),
                    situacao=Matricula.Situacao.ATIVA,
                )

                origem_ingresso = (form.cleaned_data.get("origem_ingresso") or "DIRETO").strip().upper()
                processo = None
                if origem_ingresso == "PROCESSO_SELETIVO" and municipio is not None:
                    processo_numero = (form.cleaned_data.get("processo_numero") or "").strip()
                    processo_assunto = (form.cleaned_data.get("processo_assunto") or "Ingresso de aluno").strip()
                    edital_referencia = (form.cleaned_data.get("edital_referencia") or "").strip()
                    observacao_ingresso = (form.cleaned_data.get("observacao_ingresso") or "").strip()

                    descricao_partes = [
                        f"Ingresso/matrícula inicial do aluno {aluno.nome}.",
                        f"Turma destino: {turma.nome}.",
                    ]
                    if edital_referencia:
                        descricao_partes.append(f"Edital: {edital_referencia}.")
                    if observacao_ingresso:
                        descricao_partes.append(observacao_ingresso)
                    descricao = " ".join(descricao_partes)[:1000]

                    processo, criado = ProcessoAdministrativo.objects.get_or_create(
                        municipio=municipio,
                        numero=processo_numero,
                        defaults={
                            "secretaria": getattr(turma.unidade, "secretaria", None),
                            "unidade": turma.unidade,
                            "numero": processo_numero,
                            "tipo": "INGRESSO_PROCESSO_SELETIVO",
                            "assunto": processo_assunto,
                            "solicitante_nome": aluno.nome,
                            "descricao": descricao,
                            "status": ProcessoAdministrativo.Status.CONCLUIDO,
                            "responsavel_atual": request.user if request.user.is_authenticated else None,
                            "data_abertura": timezone.localdate(),
                            "criado_por": request.user if request.user.is_authenticated else None,
                        },
                    )
                    if not criado and descricao and processo.descricao != descricao:
                        processo.descricao = descricao
                        if processo.status != ProcessoAdministrativo.Status.CONCLUIDO:
                            processo.status = ProcessoAdministrativo.Status.CONCLUIDO
                        processo.save(update_fields=["descricao", "status", "atualizado_em"])

                    ProcessoAndamento.objects.create(
                        processo=processo,
                        tipo=ProcessoAndamento.Tipo.CONCLUSAO,
                        despacho=f"Ingresso/matrícula confirmada para {aluno.nome} na turma {turma.nome}.",
                        data_evento=timezone.localdate(),
                        criado_por=request.user if request.user.is_authenticated else None,
                    )

                motivo_parts = ["Matrícula de ingressante criada no cadastro do aluno."]
                if origem_ingresso == "PROCESSO_SELETIVO":
                    motivo_parts.append("Origem: processo seletivo.")
                    if processo is not None:
                        motivo_parts.append(f"Processo: {processo.numero}.")
                    edital_ref = (form.cleaned_data.get("edital_referencia") or "").strip()
                    if edital_ref:
                        motivo_parts.append(f"Edital: {edital_ref}.")
                else:
                    motivo_parts.append("Origem: ingresso direto.")
                observacao_ingresso = (form.cleaned_data.get("observacao_ingresso") or "").strip()
                if observacao_ingresso:
                    motivo_parts.append(observacao_ingresso)
                registrar_movimentacao(
                    matricula=matricula,
                    tipo=MatriculaMovimentacao.Tipo.CRIACAO,
                    usuario=request.user if request.user.is_authenticated else None,
                    turma_origem=turma,
                    turma_destino=turma,
                    situacao_nova=matricula.situacao,
                    data_referencia=matricula.data_matricula,
                    motivo=" ".join(motivo_parts)[:900],
                )
            messages.success(request, "Aluno criado e matriculado com sucesso.")
            return redirect("educacao:aluno_detail", pk=aluno.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AlunoCreateComTurmaForm(user=request.user)

    return render(
        request,
        "educacao/aluno_form.html",
        {
            "form": form,
            "mode": "create",
            "cancel_url": reverse("educacao:aluno_list"),
            "submit_label": "Salvar",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:aluno_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


def aluno_update(request, pk: int):
    aluno_qs = scope_filter_alunos(request.user, Aluno.objects.all())
    aluno = get_object_or_404(aluno_qs, pk=pk)

    if request.method == "POST":
        form = AlunoForm(request.POST, request.FILES, instance=aluno)
        if form.is_valid():
            form.save()
            messages.success(request, "Aluno atualizado com sucesso.")
            return redirect("educacao:aluno_detail", pk=aluno.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AlunoForm(instance=aluno)

    return render(
        request,
        "educacao/aluno_form.html",
        {
            "form": form,
            "mode": "update",
            "cancel_url": reverse("educacao:aluno_list"),
            "submit_label": "Atualizar",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:aluno_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )
