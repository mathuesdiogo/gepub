from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.urls import reverse
from django.views.generic import TemplateView


@dataclass
class ListAction:
    label: str
    url: str
    icon: str | None = None
    variant: str = "btn--ghost"  # seu page_head usa "variant" tipo btn-primary


@dataclass
class TableHeader:
    label: str
    width: str | None = None


@dataclass
class TableCell:
    text: str | None = None
    url: str | None = None
    html: str | None = None
    safe: bool = False


@dataclass
class TableRow:
    cells: list[dict[str, Any]]
    can_edit: bool = False
    edit_url: str = ""


class BaseListViewGepub(LoginRequiredMixin, TemplateView):
    """
    Base padrão para páginas LIST no GEPUB UI CORE.

    Contrato esperado pelo template (já é o que você usa):
      - actions
      - q, page_obj
      - headers, rows
      - action_url, clear_url, has_filters
      - extra_filters (html)
      - autocomplete_url, autocomplete_href

    Cada tela só implementa:
      - template_name
      - model ou get_base_queryset()
      - scope_fn (ex: scope_filter_municipios)
      - search_fields / get_search_q()
      - build_headers() e build_rows()
      - perm_create / perm_edit
    """

    template_name: str = ""
    paginate_by: int = 10

    # Queryset base
    model = None  # opcional
    base_queryset: QuerySet | None = None

    # Scoping RBAC (ex: scope_filter_municipios(user, qs))
    scope_fn: Callable[[Any, QuerySet], QuerySet] | None = None

    # Busca
    q_param: str = "q"
    search_fields: list[str] = []  # ex: ["nome__icontains", "uf__icontains"]

    # URLs (names)
    url_list_name: str = ""        # ex: "org:municipio_list"
    url_create_name: str = ""      # ex: "org:municipio_create"
    url_detail_name: str = ""      # ex: "org:municipio_detail"
    url_update_name: str = ""      # ex: "org:municipio_update"
    url_autocomplete_name: str = ""  # ex: "org:municipio_autocomplete"

    # Page head
    page_title: str = ""
    page_subtitle: str = ""

    # Permissões (pluga seu can())
    can_fn: Callable[[Any, str], bool] | None = None
    perm_create: str | None = None
    perm_edit: str | None = None

    # Textos do empty-state
    empty_title: str = "Nenhum registro encontrado"
    empty_text: str = "Tente ajustar sua busca."

    # Ordenação
    ordering: str | None = None

    def get_base_queryset(self) -> QuerySet:
        if self.base_queryset is not None:
            return self.base_queryset
        if self.model is None:
            raise ValueError("Defina model=... ou base_queryset=... na ListView.")
        return self.model.objects.all()

    def get_scoped_queryset(self, qs: QuerySet) -> QuerySet:
        if self.scope_fn:
            return self.scope_fn(self.request.user, qs)
        return qs

    def get_q(self) -> str:
        return (self.request.GET.get(self.q_param) or "").strip()

    def apply_search(self, qs: QuerySet, q: str) -> QuerySet:
        if not q or not self.search_fields:
            return qs
        # OR entre fields
        from django.db.models import Q
        cond = Q()
        for f in self.search_fields:
            cond |= Q(**{f: q})
        return qs.filter(cond)

    def get_extra_filters_html(self) -> str:
        return ""

    def get_has_filters(self, q: str) -> bool:
        return bool(q) or bool(self.get_extra_filters_html())

    def user_can(self, perm: str | None) -> bool:
        if not perm:
            return False
        if not self.can_fn:
            return False
        return bool(self.can_fn(self.request.user, perm))

    def build_actions(self) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        if self.url_create_name and self.user_can(self.perm_create):
            actions.append({
                "label": "Novo",
                "url": reverse(self.url_create_name),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            })
        return actions

    def build_headers(self) -> list[dict[str, Any]]:
        return []

    def build_rows(self, page_obj) -> list[dict[str, Any]]:
        return []

    def paginate(self, qs: QuerySet):
        paginator = Paginator(qs, self.paginate_by)
        return paginator.get_page(self.request.GET.get("page"))

    def get_autocomplete(self) -> tuple[str, str]:
        if not self.url_autocomplete_name:
            return "", ""
        return (
            reverse(self.url_autocomplete_name),
            reverse(self.url_list_name) + "?q={q}",
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        q = self.get_q()
        qs = self.get_scoped_queryset(self.get_base_queryset())
        qs = self.apply_search(qs, q)

        if self.ordering:
            qs = qs.order_by(self.ordering)

        page_obj = self.paginate(qs)

        ac_url, ac_href = self.get_autocomplete()

        ctx.update({
            "actions": self.build_actions(),
            "headers": self.build_headers(),
            "rows": self.build_rows(page_obj),
            "q": q,
            "page_obj": page_obj,
            "action_url": reverse(self.url_list_name) if self.url_list_name else "",
            "clear_url": reverse(self.url_list_name) if self.url_list_name else "",
            "has_filters": self.get_has_filters(q),
            "extra_filters": self.get_extra_filters_html(),
            "autocomplete_url": ac_url,
            "autocomplete_href": ac_href,
            "empty_title": self.empty_title,
            "empty_text": self.empty_text,
            # page head
            "page_title": self.page_title,
            "page_subtitle": self.page_subtitle,
        })
        return ctx