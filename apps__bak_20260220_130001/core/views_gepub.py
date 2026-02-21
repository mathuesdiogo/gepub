# apps/core/views_gepub.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q, QuerySet
from django.shortcuts import render
from django.urls import reverse


@dataclass
class TableHeader:
    label: str
    width: str | None = None


class BaseListViewGepub(LoginRequiredMixin):
    """
    Base padrão para telas LIST no GEPUB (SUAP-like).

    Convenções:
    - template usa: page_head + filter_bar + table_shell
    - context entregue:
      q, ano, page_obj, actions, headers, rows,
      action_url, clear_url, has_filters,
      autocomplete_url, autocomplete_href,
      extra_filters (HTML), breadcrumbs
    """

    # Obrigatórios no filho
    template_name: str = ""
    url_name: str = ""          # para action_url/clear_url (ex: "educacao:turma_list")
    page_title: str = ""
    page_subtitle: str = ""

    # Tabela
    paginate_by: int = 20

    # Busca e filtros
    q_param: str = "q"
    ano_param: str = "ano"
    search_fields: list[str] = []      # ex: ["nome", "unidade__nome", ...]
    default_ano: int | None = None     # se quiser default (ex: ano atual)

    # Autocomplete (opcional)
    autocomplete_url_name: str | None = None  # ex: "educacao:turma_autocomplete"

    # Breadcrumbs (opcional)
    breadcrumbs: list[dict[str, Any]] | None = None

    # ---------- Hooks principais ----------
    def get_base_queryset(self) -> QuerySet:
        """
        Retorne o queryset base SEM filtros de q/ano (mas já pode vir com scope RBAC).
        """
        raise NotImplementedError

    def apply_filters(self, qs: QuerySet) -> QuerySet:
        """
        Filtros adicionais além de q/ano.
        """
        return qs

    def apply_search(self, qs: QuerySet, q: str) -> QuerySet:
        if not q or not self.search_fields:
            return qs

        query = Q()
        for f in self.search_fields:
            query |= Q(**{f"{f}__icontains": q})
        return qs.filter(query)

    def apply_ano(self, qs: QuerySet, ano: int | None) -> QuerySet:
        """
        Se o filho quiser filtrar por ano_letivo, pode sobrescrever aqui.
        """
        return qs

    # ---------- UI hooks ----------
    def get_actions(self) -> list[dict[str, Any]]:
        return []

    def get_headers(self) -> list[dict[str, Any]]:
        """
        Retorne uma lista no formato do seu TableShell:
        [{"label":"...", "width":"120px"}, ...]
        """
        return []

    def get_rows(self, qs_page: Iterable[Any]) -> list[dict[str, Any]]:
        """
        Monte rows no formato TableShell:
        {"cells":[{text/url OR html/safe}, ...], "can_edit":bool, "edit_url":""}
        """
        return []

    def get_extra_filters_html(self, *, ano: int | None) -> str:
        """
        HTML extra dentro da filter_bar (ex.: select de ano).
        Retorne string HTML (já “pronta”) ou "".
        """
        return ""

    def get_input_attrs(self) -> str:
        """
        Atributos extras do input de busca (autocomplete etc.).
        """
        return ""

    # ---------- Helpers ----------
    def _get_int(self, val: str | None) -> int | None:
        try:
            if val is None or val == "":
                return None
            return int(val)
        except Exception:
            return None

    def get(self, request, *args, **kwargs):
        q = (request.GET.get(self.q_param) or "").strip()
        ano = self._get_int(request.GET.get(self.ano_param))
        if ano is None:
            ano = self.default_ano

        qs = self.get_base_queryset()
        qs = self.apply_ano(qs, ano)
        qs = self.apply_filters(qs)
        qs = self.apply_search(qs, q)

        paginator = Paginator(qs, self.paginate_by)
        page_obj = paginator.get_page(request.GET.get("page"))

        headers = self.get_headers()
        rows = self.get_rows(page_obj.object_list)

        action_url = reverse(self.url_name) if self.url_name else ""
        clear_url = reverse(self.url_name) if self.url_name else ""

        autocomplete_url = reverse(self.autocomplete_url_name) if self.autocomplete_url_name else ""
        # mantém padrão que você já usa: "?q={q}" e pode acrescentar &ano=...
        autocomplete_href = (reverse(self.url_name) + "?q={q}") if self.url_name else ""

        extra_filters = self.get_extra_filters_html(ano=ano)

        ctx = {
            "q": q,
            "ano": ano,
            "page_obj": page_obj,

            "actions": self.get_actions(),
            "headers": headers,
            "rows": rows,

            "action_url": action_url,
            "clear_url": clear_url,
            "has_filters": bool(q or ano),

            "autocomplete_url": autocomplete_url,
            "autocomplete_href": autocomplete_href,

            "extra_filters": extra_filters,
            "input_attrs": self.get_input_attrs(),

            "breadcrumbs": self.breadcrumbs,
            "page_title": self.page_title,
            "page_subtitle": self.page_subtitle,
        }

        return render(request, self.template_name, ctx)