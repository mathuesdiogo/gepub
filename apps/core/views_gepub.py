from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View

from apps.core.rbac import can


@dataclass
class TableHeader:
    label: str
    width: str = ""


class GepubViewMixin:
    perm: str = "core.view"
    title: str = ""
    subtitle: str = ""
    back_url_name: str = ""
    manage_perm: str = ""

    def has_manage(self, user) -> bool:
        return bool(self.manage_perm) and can(user, self.manage_perm)

    def get_back_url(self) -> str:
        return reverse(self.back_url_name) if self.back_url_name else reverse("core:dashboard")

    def get_actions(self, request: HttpRequest, **kwargs) -> List[Dict[str, Any]]:
        return [
            {"label": "Voltar", "url": self.get_back_url(), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        ]


@method_decorator(login_required, name="dispatch")
class BaseListViewGepub(GepubViewMixin, View):
    template_name: str = "core/list_base.html"
    paginate_by: int = 20
    search_param: str = "q"

    empty_title: str = "Nenhum registro"
    empty_text: str = "Não há registros para exibir."

    def get_queryset(self, request: HttpRequest):
        raise NotImplementedError

    def apply_search(self, qs, q: str):
        return qs

    def get_headers(self, request: HttpRequest) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def get_rows(self, request: HttpRequest, page_obj) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def get_extra_filters_html(self, request: HttpRequest, **kwargs) -> str:
        return ""

    def get_filter_placeholder(self) -> str:
        return "Digite para buscar..."

    def get_input_attrs(self, request: HttpRequest, **kwargs) -> str:
        # Para autocomplete etc: retorne string com attrs (ex: data-autocomplete-url="..." ...)
        return ""

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        q = (request.GET.get(self.search_param) or "").strip()

        qs = self.get_queryset(request)
        if q:
            qs = self.apply_search(qs, q)

        paginator = Paginator(qs, self.paginate_by)
        page_obj = paginator.get_page(request.GET.get("page"))

        context = {
            "title": self.title,
            "subtitle": self.subtitle,
            "actions": self.get_actions(request, **kwargs),

            "q": q,
            "action_url": request.path,
            "clear_url": request.path,
            "has_filters": bool(q),
            "placeholder": self.get_filter_placeholder(),
            "extra_filters": self.get_extra_filters_html(request, q=q, **kwargs),
            "input_attrs": self.get_input_attrs(request, q=q, **kwargs),

            "headers": self.get_headers(request),
            "rows": self.get_rows(request, page_obj),

            "page_obj": page_obj,
            "empty_title": self.empty_title,
            "empty_text": self.empty_text,
        }
        return render(request, self.template_name, context)


@method_decorator(login_required, name="dispatch")
class BaseCreateViewGepub(GepubViewMixin, View):
    template_name: str = "core/form_base.html"
    form_class = None
    submit_label: str = "Salvar"

    def get_form(self, request: HttpRequest, *args, **kwargs):
        if not self.form_class:
            raise NotImplementedError("Defina form_class")
        return self.form_class(*args, **kwargs)

    def get_cancel_url(self, request: HttpRequest, **kwargs) -> str:
        return self.get_back_url()

    def get_success_url(self, request: HttpRequest, obj=None) -> str:
        return self.get_back_url()

    def form_valid(self, request: HttpRequest, form):
        obj = form.save()
        messages.success(request, "Salvo com sucesso.")
        return redirect(self.get_success_url(request, obj=obj))

    def form_invalid(self, request: HttpRequest, form):
        messages.error(request, "Corrija os erros do formulário.")
        return render(request, self.template_name, self.get_context_data(request, form=form, mode="create"))

    def get_context_data(self, request: HttpRequest, **kwargs) -> Dict[str, Any]:
        return {
            "title": self.title or "Novo",
            "subtitle": self.subtitle or "",
            "actions": self.get_actions(request),
            "form": kwargs.get("form"),
            "mode": kwargs.get("mode", "create"),
            "cancel_url": self.get_cancel_url(request),
            "submit_label": self.submit_label,
        }

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        form = self.get_form(request)
        return render(request, self.template_name, self.get_context_data(request, form=form, mode="create"))

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        form = self.get_form(request, data=request.POST, files=getattr(request, "FILES", None))
        if form.is_valid():
            return self.form_valid(request, form)
        return self.form_invalid(request, form)


@method_decorator(login_required, name="dispatch")
class BaseUpdateViewGepub(GepubViewMixin, View):
    template_name: str = "core/form_base.html"
    form_class = None
    model = None
    submit_label: str = "Atualizar"

    def get_object(self, request: HttpRequest, pk: int):
        if not self.model:
            raise NotImplementedError("Defina model")
        return self.model.objects.get(pk=pk)

    def get_form(self, request: HttpRequest, instance=None, *args, **kwargs):
        if not self.form_class:
            raise NotImplementedError("Defina form_class")
        return self.form_class(*args, instance=instance, **kwargs)

    def get_cancel_url(self, request: HttpRequest, obj=None, **kwargs) -> str:
        return self.get_back_url()

    def get_success_url(self, request: HttpRequest, obj=None) -> str:
        return self.get_back_url()

    def form_valid(self, request: HttpRequest, form, obj=None):
        obj = form.save()
        messages.success(request, "Atualizado com sucesso.")
        return redirect(self.get_success_url(request, obj=obj))

    def form_invalid(self, request: HttpRequest, form, obj=None):
        messages.error(request, "Corrija os erros do formulário.")
        return render(request, self.template_name, self.get_context_data(request, form=form, obj=obj, mode="update"))

    def get_context_data(self, request: HttpRequest, **kwargs) -> Dict[str, Any]:
        return {
            "title": self.title or "Editar",
            "subtitle": self.subtitle or "",
            "actions": self.get_actions(request, obj=kwargs.get("obj")),
            "form": kwargs.get("form"),
            "obj": kwargs.get("obj"),
            "mode": kwargs.get("mode", "update"),
            "cancel_url": self.get_cancel_url(request, obj=kwargs.get("obj")),
            "submit_label": self.submit_label,
        }

    def get(self, request: HttpRequest, pk: int, *args, **kwargs) -> HttpResponse:
        obj = self.get_object(request, pk)
        form = self.get_form(request, instance=obj)
        return render(request, self.template_name, self.get_context_data(request, form=form, obj=obj, mode="update"))

    def post(self, request: HttpRequest, pk: int, *args, **kwargs) -> HttpResponse:
        obj = self.get_object(request, pk)
        form = self.get_form(request, instance=obj, data=request.POST, files=getattr(request, "FILES", None))
        if form.is_valid():
            return self.form_valid(request, form, obj=obj)
        return self.form_invalid(request, form, obj=obj)


@method_decorator(login_required, name="dispatch")
class BaseDetailViewGepub(GepubViewMixin, View):
    template_name: str = "core/detail_base.html"
    model = None

    def get_object(self, request: HttpRequest, pk: int):
        if not self.model:
            raise NotImplementedError("Defina model")
        return self.model.objects.get(pk=pk)

    def get_fields(self, request: HttpRequest, obj) -> List[Tuple[str, Any]]:
        return []

    def get_pills(self, request: HttpRequest, obj) -> List[Tuple[str, Any]]:
        return []

    def get_context_data(self, request: HttpRequest, obj, **kwargs) -> Dict[str, Any]:
        return {
            "title": self.title or str(obj),
            "subtitle": self.subtitle or "",
            "actions": self.get_actions(request, obj=obj),
            "obj": obj,
            "fields": self.get_fields(request, obj),
            "pills": self.get_pills(request, obj),
        }

    def get(self, request: HttpRequest, pk: int, *args, **kwargs) -> HttpResponse:
        obj = self.get_object(request, pk)
        return render(request, self.template_name, self.get_context_data(request, obj=obj))
