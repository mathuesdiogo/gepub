from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import TipoNecessidadeForm
from .models import TipoNecessidade


@login_required
def index(request):
    return render(request, "nee/index.html")


@login_required
def tipo_list(request):
    q = (request.GET.get("q") or "").strip()

    qs = TipoNecessidade.objects.all()
    if q:
        qs = qs.filter(Q(nome__icontains=q))

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "nee/tipo_list.html", {"q": q, "page_obj": page_obj})


@login_required
def tipo_detail(request, pk: int):
    tipo = get_object_or_404(TipoNecessidade, pk=pk)
    return render(request, "nee/tipo_detail.html", {"tipo": tipo})


@login_required
def tipo_create(request):
    if request.method == "POST":
        form = TipoNecessidadeForm(request.POST)
        if form.is_valid():
            tipo = form.save()
            messages.success(request, "Tipo de necessidade criado com sucesso.")
            return redirect("nee:tipo_detail", pk=tipo.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = TipoNecessidadeForm()

    return render(request, "nee/tipo_form.html", {"form": form, "mode": "create"})


@login_required
def tipo_update(request, pk: int):
    tipo = get_object_or_404(TipoNecessidade, pk=pk)

    if request.method == "POST":
        form = TipoNecessidadeForm(request.POST, instance=tipo)
        if form.is_valid():
            form.save()
            messages.success(request, "Tipo de necessidade atualizado com sucesso.")
            return redirect("nee:tipo_detail", pk=tipo.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = TipoNecessidadeForm(instance=tipo)

    return render(
        request,
        "nee/tipo_form.html",
        {"form": form, "mode": "update", "tipo": tipo},
    )
