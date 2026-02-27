from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.rbac import scope_filter_turmas

from .forms import TurmaForm
from .models import Turma


def turma_create(request):
    if request.method == "POST":
        form = TurmaForm(request.POST, user=request.user)
        if form.is_valid():
            turma = form.save()
            messages.success(request, "Turma criada com sucesso.")
            return redirect("educacao:turma_detail", pk=turma.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = TurmaForm(user=request.user)

    return render(
        request,
        "educacao/turma_form.html",
        {
            "form": form,
            "mode": "create",
            "cancel_url": reverse("educacao:turma_list"),
            "submit_label": "Salvar",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:turma_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


def turma_update(request, pk: int):
    qs = Turma.objects.select_related(
        "unidade",
        "unidade__secretaria",
        "unidade__secretaria__municipio",
    )
    qs = scope_filter_turmas(request.user, qs)
    turma = get_object_or_404(qs, pk=pk)

    if request.method == "POST":
        form = TurmaForm(request.POST, instance=turma, user=request.user)
        if form.is_valid():
            turma = form.save()
            messages.success(request, "Turma atualizada com sucesso.")
            return redirect("educacao:turma_detail", pk=turma.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = TurmaForm(instance=turma, user=request.user)

    return render(
        request,
        "educacao/turma_form.html",
        {
            "form": form,
            "mode": "update",
            "turma": turma,
            "cancel_url": reverse("educacao:turma_list"),
            "submit_label": "Atualizar",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:turma_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )
