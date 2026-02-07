from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import MunicipioForm
from .models import Municipio


@login_required
def index(request):
    return render(request, "org/index.html")


@login_required
def municipio_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = Municipio.objects.all()

    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(uf__icontains=q))

    paginator = Paginator(qs, 10)  # 10 por página (padrão SUAP)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "org/municipio_list.html",
        {
            "q": q,
            "page_obj": page_obj,
        },
    )


@login_required
def municipio_detail(request, pk: int):
    municipio = get_object_or_404(Municipio, pk=pk)
    return render(request, "org/municipio_detail.html", {"municipio": municipio})


@login_required
def municipio_create(request):
    if request.method == "POST":
        form = MunicipioForm(request.POST)
        if form.is_valid():
            municipio = form.save()
            messages.success(request, "Município criado com sucesso.")
            return redirect("org:municipio_detail", pk=municipio.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = MunicipioForm()

    return render(
        request,
        "org/municipio_form.html",
        {"form": form, "mode": "create"},
    )


@login_required
def municipio_update(request, pk: int):
    municipio = get_object_or_404(Municipio, pk=pk)

    if request.method == "POST":
        form = MunicipioForm(request.POST, instance=municipio)
        if form.is_valid():
            form.save()
            messages.success(request, "Município atualizado com sucesso.")
            return redirect("org:municipio_detail", pk=municipio.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = MunicipioForm(instance=municipio)

    return render(
        request,
        "org/municipio_form.html",
        {"form": form, "mode": "update", "municipio": municipio},
    )
