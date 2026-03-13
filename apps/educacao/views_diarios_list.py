from __future__ import annotations

from django.db.models import Q
from django.http import HttpResponseForbidden
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from apps.core.rbac import can, is_professor_profile_role, scope_filter_turmas
from apps.core.views_gepub import BaseListViewGepub

from .models import Turma
from .models_diario import DiarioTurma


def _is_professor(user) -> bool:
    return is_professor_profile_role(getattr(getattr(user, "profile", None), "role", None))


class DiarioListView(BaseListViewGepub):
    template_name = "educacao/diario_list.html"
    url_name = "educacao:meus_diarios"

    page_title = "Diários de Classe"
    page_subtitle = "Acesso aos diários por turma"

    paginate_by = 20
    default_ano = timezone.now().year

    def dispatch(self, request, *args, **kwargs):
        if not can(request.user, "educacao.view"):
            return HttpResponseForbidden("403 — Você não tem permissão para acessar Educação.")
        return super().dispatch(request, *args, **kwargs)

    def get_base_queryset(self):
        user = self.request.user
        is_prof = _is_professor(user)

        if is_prof:
            qs = (
                DiarioTurma.objects.select_related("turma", "turma__unidade")
                .filter(professor=user)
            )
        else:
            turmas_scope = scope_filter_turmas(user, Turma.objects.all())
            qs = (
                DiarioTurma.objects.select_related("turma", "turma__unidade", "professor")
                .filter(turma__in=turmas_scope)
            )

        return qs.order_by("-ano_letivo", "turma__nome")

    def apply_ano(self, qs, ano, **kwargs):
        if ano:
            return qs.filter(ano_letivo=int(ano))
        return qs

    def apply_search(self, qs, q: str, **kwargs):
        if not q:
            return qs

        if _is_professor(self.request.user):
            return qs.filter(
                Q(turma__nome__icontains=q)
                | Q(turma__unidade__nome__icontains=q)
            )

        return qs.filter(
            Q(turma__nome__icontains=q)
            | Q(turma__unidade__nome__icontains=q)
            | Q(professor__username__icontains=q)
        )

    def get_headers(self, **kwargs):
        headers = [
            {"label": "Turma"},
            {"label": "Unidade"},
            {"label": "Ano", "width": "120px"},
        ]
        if not _is_professor(self.request.user):
            headers.append({"label": "Professor", "width": "220px"})
        return headers

    def get_rows(self, objs, **kwargs):
        rows = []
        is_prof = _is_professor(self.request.user)
        for d in objs:
            cells = [
                {"text": d.turma.nome, "url": reverse("educacao:diario_detail", args=[d.pk])},
                {"text": getattr(getattr(d.turma, "unidade", None), "nome", "—")},
                {"text": str(d.ano_letivo)},
            ]
            if not is_prof:
                cells.append({"text": getattr(getattr(d, "professor", None), "username", "—")})
            rows.append({"cells": cells, "can_edit": False, "edit_url": ""})
        return rows

    def get_extra_filters_html(self, *, ano=None, **kwargs):
        qs = self.get_base_queryset()
        anos = list(qs.order_by("-ano_letivo").values_list("ano_letivo", flat=True).distinct())[:12]
        if not anos:
            return ""
        options = [format_html('<option value=""{}>{}</option>', " selected" if not ano else "", "Todos os anos")]
        options.extend(
            format_html('<option value="{}"{}>{}</option>', a, " selected" if str(ano) == str(a) else "", a)
            for a in anos
        )
        options_html = format_html_join("", "{}", ((item,) for item in options))
        return str(
            format_html(
                '<div class="filter-bar__field"><label class="small">Ano letivo</label><select name="ano">{}</select></div>',
                options_html,
            )
        )
