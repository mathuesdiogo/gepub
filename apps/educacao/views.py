from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import TurmaForm
from .models import Turma


@login_required
def index(request):
    return render(request, "educacao/index.html")


@login_required
def turma_list(request):
    q = (request.GET.get("q") or "").strip()
    ano = (request.GET.get("ano") or "").strip()

    qs = Turma.objects.select_related("unidade", "unidade__secretaria", "unidade__secretaria__municipio")

    if ano.isdigit():
        qs = qs.filter(ano_letivo=int(ano))

    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(unidade__nome__icontains=q)
            | Q(unidade__secretaria__nome__icontains=q)
            | Q(unidade__secretaria__municipio__nome__icontains=q)
        )

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "educacao/turma_list.html",
        {"q": q, "ano": ano, "page_obj": page_obj},
    )


@login_required
def turma_detail(request, pk: int):
    turma = get_object_or_404(
        Turma.objects.select_related("unidade", "unidade__secretaria", "unidade__secretaria__municipio"),
        pk=pk,
    )
    return render(request, "educacao/turma_detail.html", {"turma": turma})


@login_required
def turma_create(request):
    if request.method == "POST":
        form = TurmaForm(request.POST)
        if form.is_valid():
            turma = form.save()
            messages.success(request, "Turma criada com sucesso.")
            return redirect("educacao:turma_detail", pk=turma.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = TurmaForm()

    return render(request, "educacao/turma_form.html", {"form": form, "mode": "create"})


@login_required
def turma_update(request, pk: int):
    turma = get_object_or_404(Turma, pk=pk)

    if request.method == "POST":
        form = TurmaForm(request.POST, instance=turma)
        if form.is_valid():
            form.save()
            messages.success(request, "Turma atualizada com sucesso.")
            return redirect("educacao:turma_detail", pk=turma.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = TurmaForm(instance=turma)

    return render(request, "educacao/turma_form.html", {"form": form, "mode": "update", "turma": turma})
