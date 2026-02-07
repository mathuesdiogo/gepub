from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import MunicipioForm, SecretariaForm
from .models import Municipio, Secretaria



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
def secretaria_list(request):
    q = (request.GET.get("q") or "").strip()
    municipio_id = (request.GET.get("municipio") or "").strip()

    qs = Secretaria.objects.select_related("municipio").all()

    if municipio_id.isdigit():
        qs = qs.filter(municipio_id=int(municipio_id))

    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(sigla__icontains=q) | Q(municipio__nome__icontains=q))

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    municipios = Municipio.objects.filter(ativo=True).order_by("nome")

    return render(
        request,
        "org/secretaria_list.html",
        {"q": q, "municipio_id": municipio_id, "page_obj": page_obj, "municipios": municipios},
    )


@login_required
def secretaria_detail(request, pk: int):
    secretaria = get_object_or_404(Secretaria.objects.select_related("municipio"), pk=pk)
    return render(request, "org/secretaria_detail.html", {"secretaria": secretaria})


@login_required
def secretaria_create(request):
    if request.method == "POST":
        form = SecretariaForm(request.POST)
        if form.is_valid():
            secretaria = form.save()
            messages.success(request, "Secretaria criada com sucesso.")
            return redirect("org:secretaria_detail", pk=secretaria.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = SecretariaForm()

    return render(request, "org/secretaria_form.html", {"form": form, "mode": "create"})


@login_required
def secretaria_update(request, pk: int):
    secretaria = get_object_or_404(Secretaria, pk=pk)

    if request.method == "POST":
        form = SecretariaForm(request.POST, instance=secretaria)
        if form.is_valid():
            form.save()
            messages.success(request, "Secretaria atualizada com sucesso.")
            return redirect("org:secretaria_detail", pk=secretaria.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = SecretariaForm(instance=secretaria)

    return render(
        request,
        "org/secretaria_form.html",
        {"form": form, "mode": "update", "secretaria": secretaria},
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
