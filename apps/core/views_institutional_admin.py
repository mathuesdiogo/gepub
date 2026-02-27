from __future__ import annotations

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.core.decorators import require_perm
from apps.core.forms import (
    InstitutionalMethodStepForm,
    InstitutionalPageConfigForm,
    InstitutionalServiceCardForm,
    InstitutionalSlideForm,
)
from apps.core.models import (
    InstitutionalMethodStep,
    InstitutionalPageConfig,
    InstitutionalServiceCard,
    InstitutionalSlide,
)


def _get_or_create_page_config() -> InstitutionalPageConfig:
    page = InstitutionalPageConfig.objects.filter(ativo=True).order_by("-atualizado_em", "-id").first()
    if page:
        return page

    page = InstitutionalPageConfig.objects.order_by("-atualizado_em", "-id").first()
    if page:
        page.ativo = True
        page.save(update_fields=["ativo", "atualizado_em"])
        return page

    return InstitutionalPageConfig.objects.create(nome="Página Institucional Padrão", ativo=True)


@require_perm("system.admin_django")
@require_http_methods(["GET", "POST"])
def institutional_admin(request):
    page = _get_or_create_page_config()
    form = InstitutionalPageConfigForm(request.POST or None, request.FILES or None, instance=page)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Configuração institucional atualizada.")
        return redirect("core:institutional_admin")

    slides = page.slides.all().order_by("ordem", "id")
    method_steps = page.metodo_passos.all().order_by("ordem", "id")
    service_cards = page.servicos.all().order_by("ordem", "id")

    return render(
        request,
        "core/institutional_admin.html",
        {
            "title": "Editor da Institucional",
            "subtitle": "Gerencie textos, logo, slides e conteúdo da home pública",
            "actions": [
                {
                    "label": "Ver página pública",
                    "url": reverse("core:institucional_public") + "?preview=1",
                    "icon": "fa-solid fa-arrow-up-right-from-square",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Voltar",
                    "url": reverse("core:dashboard"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
            "form": form,
            "page": page,
            "slides": slides,
            "method_steps": method_steps,
            "service_cards": service_cards,
            "cancel_url": reverse("core:dashboard"),
            "submit_label": "Salvar alterações",
            "enctype": "multipart/form-data",
        },
    )


@require_perm("system.admin_django")
@require_http_methods(["GET", "POST"])
def institutional_slide_create(request):
    page = _get_or_create_page_config()
    form = InstitutionalSlideForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        slide = form.save(commit=False)
        slide.pagina = page
        slide.save()
        messages.success(request, "Slide adicionado.")
        return redirect("core:institutional_admin")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo slide",
            "subtitle": "Adicione um novo slide na home pública",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("core:institutional_admin"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
            "form": form,
            "cancel_url": reverse("core:institutional_admin"),
            "submit_label": "Salvar slide",
            "enctype": "multipart/form-data",
        },
    )


@require_perm("system.admin_django")
@require_http_methods(["GET", "POST"])
def institutional_slide_update(request, pk: int):
    slide = get_object_or_404(InstitutionalSlide, pk=pk)
    form = InstitutionalSlideForm(request.POST or None, request.FILES or None, instance=slide)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Slide atualizado.")
        return redirect("core:institutional_admin")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Editar slide",
            "subtitle": "Atualize conteúdo e ordem do slide",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("core:institutional_admin"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
            "form": form,
            "cancel_url": reverse("core:institutional_admin"),
            "submit_label": "Salvar slide",
            "enctype": "multipart/form-data",
        },
    )


@require_perm("system.admin_django")
@require_http_methods(["POST"])
def institutional_slide_delete(request, pk: int):
    slide = get_object_or_404(InstitutionalSlide, pk=pk)
    slide.delete()
    messages.success(request, "Slide removido.")
    return redirect("core:institutional_admin")


@require_perm("system.admin_django")
@require_http_methods(["GET", "POST"])
def institutional_method_step_create(request):
    page = _get_or_create_page_config()
    form = InstitutionalMethodStepForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        step = form.save(commit=False)
        step.pagina = page
        step.save()
        messages.success(request, "Passo do método adicionado.")
        return redirect("core:institutional_admin")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo passo do método",
            "subtitle": "Adicione uma etapa no fluxo de implantação",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("core:institutional_admin"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
            "form": form,
            "cancel_url": reverse("core:institutional_admin"),
            "submit_label": "Salvar passo",
        },
    )


@require_perm("system.admin_django")
@require_http_methods(["GET", "POST"])
def institutional_method_step_update(request, pk: int):
    step = get_object_or_404(InstitutionalMethodStep, pk=pk)
    form = InstitutionalMethodStepForm(request.POST or None, instance=step)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Passo do método atualizado.")
        return redirect("core:institutional_admin")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Editar passo do método",
            "subtitle": "Atualize título, descrição e ordem",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("core:institutional_admin"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
            "form": form,
            "cancel_url": reverse("core:institutional_admin"),
            "submit_label": "Salvar passo",
        },
    )


@require_perm("system.admin_django")
@require_http_methods(["POST"])
def institutional_method_step_delete(request, pk: int):
    step = get_object_or_404(InstitutionalMethodStep, pk=pk)
    step.delete()
    messages.success(request, "Passo removido.")
    return redirect("core:institutional_admin")


@require_perm("system.admin_django")
@require_http_methods(["GET", "POST"])
def institutional_service_card_create(request):
    page = _get_or_create_page_config()
    form = InstitutionalServiceCardForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        service = form.save(commit=False)
        service.pagina = page
        service.save()
        messages.success(request, "Card de serviço adicionado.")
        return redirect("core:institutional_admin")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo card de serviço",
            "subtitle": "Adicione um item na grade de serviços",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("core:institutional_admin"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
            "form": form,
            "cancel_url": reverse("core:institutional_admin"),
            "submit_label": "Salvar card",
        },
    )


@require_perm("system.admin_django")
@require_http_methods(["GET", "POST"])
def institutional_service_card_update(request, pk: int):
    service = get_object_or_404(InstitutionalServiceCard, pk=pk)
    form = InstitutionalServiceCardForm(request.POST or None, instance=service)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Card de serviço atualizado.")
        return redirect("core:institutional_admin")

    return render(
        request,
        "core/form_base.html",
        {
            "title": "Editar card de serviço",
            "subtitle": "Atualize conteúdo e ordem do card",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("core:institutional_admin"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
            "form": form,
            "cancel_url": reverse("core:institutional_admin"),
            "submit_label": "Salvar card",
        },
    )


@require_perm("system.admin_django")
@require_http_methods(["POST"])
def institutional_service_card_delete(request, pk: int):
    service = get_object_or_404(InstitutionalServiceCard, pk=pk)
    service.delete()
    messages.success(request, "Card removido.")
    return redirect("core:institutional_admin")
