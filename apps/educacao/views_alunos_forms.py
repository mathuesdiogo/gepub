from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.billing.services import MetricaLimite, verificar_limite_municipio
from apps.core.rbac import scope_filter_alunos

from .forms import AlunoCreateComTurmaForm, AlunoForm
from .models import Aluno, Matricula


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
                Matricula.objects.create(
                    aluno=aluno,
                    turma=turma,
                    data_matricula=timezone.localdate(),
                    situacao=Matricula.Situacao.ATIVA,
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
