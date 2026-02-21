# apps/educacao/views_turmas_list.py
from __future__ import annotations

from django.urls import reverse
from django.utils import timezone

from apps.core.rbac import can, get_profile, is_admin, scope_filter_turmas
from apps.core.views_gepub import BaseListViewGepub
from apps.educacao.models import Turma


class TurmaListView(BaseListViewGepub):
    template_name = "educacao/turma_list.html"
    url_name = "educacao:turma_list"

    page_title = "Turmas"
    page_subtitle = "Gerencie as turmas por unidade e ano letivo"

    paginate_by = 20

    autocomplete_url_name = "educacao:turma_autocomplete"

    # Busca (ajusta conforme seus relacionamentos reais)
    search_fields = [
        "nome",
        "unidade__nome",
        "unidade__secretaria__nome",
        "unidade__secretaria__municipio__nome",
    ]

    default_ano = timezone.now().year

    def get_base_queryset(self):
        # escopo RBAC
        qs = scope_filter_turmas(self.request.user, Turma.objects.all())
        # se tiver relacionamentos, otimiza
        return qs.select_related("unidade", "unidade__secretaria", "unidade__secretaria__municipio")

    def apply_ano(self, qs, ano: int | None):
        # seu modelo usa ano_letivo (pelo dashboard)
        if ano:
            return qs.filter(ano_letivo=ano)
        return qs

    def get_actions(self):
        actions = [
            {
                "label": "Voltar",
                "url": reverse("educacao:index"),
                "icon": "fa-solid fa-arrow-left",
                "variant": "btn--ghost",
            }
        ]
        if can(self.request.user, "educacao.manage") or is_admin(self.request.user):
            actions.append({
                "label": "Nova Turma",
                "url": reverse("educacao:turma_create"),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            })
        return actions

    def get_headers(self):
        # bate com seu template de turmas (ele já passa ano=ano no table_shell) :contentReference[oaicite:0]{index=0}
        return [
            {"label": "Turma"},
            {"label": "Ano", "width": "110px"},
            {"label": "Unidade"},
            {"label": "Secretaria"},
            {"label": "Município"},
            {"label": "Ativo", "width": "110px"},
        ]

    def get_rows(self, qs_page):
        rows = []
        user = self.request.user
        can_edit_global = bool(can(user, "educacao.manage") or is_admin(user))

        for t in qs_page:
            ativo = getattr(t, "ativo", True)
            ativo_html = (
                '<span class="badge badge--success">Sim</span>'
                if ativo else
                '<span class="badge badge--muted">Não</span>'
            )

            unidade = getattr(t, "unidade", None)
            secretaria = getattr(unidade, "secretaria", None) if unidade else None
            municipio = getattr(secretaria, "municipio", None) if secretaria else None

            edit_url = reverse("educacao:turma_update", args=[t.pk]) if can_edit_global else ""

            rows.append({
                "cells": [
                    {"text": t.nome, "url": reverse("educacao:turma_detail", args=[t.pk])},
                    {"html": f'<span class="text-center">{getattr(t, "ano_letivo", "—")}</span>', "safe": True},
                    {"text": getattr(unidade, "nome", "—") or "—", "url": ""},
                    {"text": getattr(secretaria, "nome", "—") or "—", "url": ""},
                    {"text": getattr(municipio, "nome", "—") or "—", "url": ""},
                    {"html": f'<span class="text-center">{ativo_html}</span>', "safe": True},
                ],
                "can_edit": bool(edit_url),
                "edit_url": edit_url,
            })

        return rows

    def get_extra_filters_html(self, *, ano: int | None) -> str:
        # select de ano (SUAP-like)
        # pega anos existentes dentro do escopo (não fica oferecendo ano vazio)
        qs = self.get_base_queryset()
        anos = list(
            qs.order_by("-ano_letivo")
              .values_list("ano_letivo", flat=True)
              .distinct()
        )[:12]

        if not anos:
            return ""

        options = []
        # opção "Todos" (mantém q)
        selected = "selected" if not ano else ""
        options.append(f'<option value="" {selected}>Todos os anos</option>')

        for a in anos:
            sel = "selected" if ano == a else ""
            options.append(f'<option value="{a}" {sel}>{a}</option>')

        # Esse HTML entra no extra_filters do seu filter_bar (como você já faz) :contentReference[oaicite:1]{index=1}
        return f"""
<div class="filter-bar__field">
  <label class="small">Ano letivo</label>
  <select name="ano">
    {''.join(options)}
  </select>
</div>
"""

    def get_input_attrs(self) -> str:
        # mantém padrão de autocomplete do seu filter_bar (data-autocomplete-url/href)
        return (
            'data-autocomplete-url="' + reverse("educacao:turma_autocomplete") + '" '
            'data-autocomplete-href="' + (reverse("educacao:turma_list") + '?q={q}') + '"'
        )