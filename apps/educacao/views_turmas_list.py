from __future__ import annotations

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape, format_html, format_html_join

from apps.core.rbac import can, is_admin, scope_filter_turmas
from apps.core.views_gepub import BaseListViewGepub
from apps.core.exports import export_csv, export_pdf_table

from .models import Turma


class TurmaListView(BaseListViewGepub):
    template_name = "educacao/turma_list.html"
    url_name = "educacao:turma_list"

    page_title = "Turmas"
    page_subtitle = "Gerencie as turmas por unidade e ano letivo"

    paginate_by = 20
    autocomplete_url_name = "educacao:api_turmas_suggest"
    default_ano = timezone.now().year

    @staticmethod
    def _ensure_selected_choice(choices, selected, all_choices):
        if not selected:
            return choices
        values = {value for value, _ in choices}
        if selected in values:
            return choices
        all_map = dict(all_choices)
        label = all_map.get(selected, selected)
        return [*choices, (selected, f"{label} (legado)")]

    def get_base_queryset(self):
        qs = (
            Turma.objects.select_related(
                "unidade",
                "unidade__secretaria",
                "unidade__secretaria__municipio",
                "curso",
                "matriz_curricular",
            )
            .only(
                "id",
                "nome",
                "ano_letivo",
                "turno",
                "modalidade",
                "etapa",
                "serie_ano",
                "forma_oferta",
                "ativo",
                "curso_id",
                "curso__nome",
                "matriz_curricular_id",
                "matriz_curricular__nome",
                "unidade_id",
                "unidade__nome",
                "unidade__secretaria__nome",
                "unidade__secretaria__municipio__nome",
            )
            .filter(unidade__tipo="EDUCACAO")
        )
        return scope_filter_turmas(self.request.user, qs)

    def apply_ano(self, qs, ano, **kwargs):
        if ano:
            return qs.filter(ano_letivo=int(ano))
        return qs

    def apply_search(self, qs, q: str, **kwargs):
        modalidade = (self.request.GET.get("modalidade") or "").strip()
        etapa = (self.request.GET.get("etapa") or "").strip()
        if not q:
            filtered = qs
        else:
            filtered = qs.filter(
                Q(nome__icontains=q)
                | Q(unidade__nome__icontains=q)
                | Q(unidade__secretaria__nome__icontains=q)
                | Q(unidade__secretaria__municipio__nome__icontains=q)
                | Q(matriz_curricular__nome__icontains=q)
                | Q(curso__nome__icontains=q)
                | Q(modalidade__icontains=q)
                | Q(etapa__icontains=q)
                | Q(serie_ano__icontains=q)
            )
        if modalidade:
            filtered = filtered.filter(modalidade=modalidade)
        if etapa:
            filtered = filtered.filter(etapa=etapa)
        return filtered

    def get(self, request, *args, **kwargs):
        q = (request.GET.get("q") or "").strip()
        ano = (request.GET.get("ano") or "").strip()
        modalidade = (request.GET.get("modalidade") or "").strip()
        etapa = (request.GET.get("etapa") or "").strip()
        serie = (request.GET.get("serie") or "").strip()
        export = (request.GET.get("export") or "").strip().lower()

        qs = self.get_base_queryset()
        if ano.isdigit():
            qs = qs.filter(ano_letivo=int(ano))
        if modalidade:
            qs = qs.filter(modalidade=modalidade)
        if etapa:
            qs = qs.filter(etapa=etapa)
        if serie:
            qs = qs.filter(serie_ano=serie)
        qs = self.apply_search(qs, q)

        if export in ("csv", "pdf"):
            turmas_export = qs.order_by("-ano_letivo", "nome")

            headers_export = [
                "Turma",
                "Ano",
                "Turno",
                "Modalidade",
                "Etapa",
                "Série/Ano",
                "Matriz",
                "Atividade Extra",
                "Oferta",
                "Unidade",
                "Secretaria",
                "Município",
                "Ativo",
            ]
            rows_export = []
            for t in turmas_export:
                rows_export.append([
                    t.nome or "—",
                    str(t.ano_letivo or "—"),
                    t.get_turno_display() if hasattr(t, "get_turno_display") else (getattr(t, "turno", "") or "—"),
                    t.get_modalidade_display() if hasattr(t, "get_modalidade_display") else (getattr(t, "modalidade", "") or "—"),
                    t.get_etapa_display() if hasattr(t, "get_etapa_display") else (getattr(t, "etapa", "") or "—"),
                    t.get_serie_ano_display() if hasattr(t, "get_serie_ano_display") else (getattr(t, "serie_ano", "") or "—"),
                    getattr(getattr(t, "matriz_curricular", None), "nome", "—"),
                    getattr(getattr(t, "curso", None), "nome", "—"),
                    t.get_forma_oferta_display() if hasattr(t, "get_forma_oferta_display") else (getattr(t, "forma_oferta", "") or "—"),
                    getattr(getattr(t, "unidade", None), "nome", "—"),
                    getattr(getattr(getattr(t, "unidade", None), "secretaria", None), "nome", "—"),
                    getattr(getattr(getattr(getattr(t, "unidade", None), "secretaria", None), "municipio", None), "nome", "—"),
                    "Sim" if getattr(t, "ativo", False) else "Não",
                ])

            if export == "csv":
                return export_csv("turmas.csv", headers_export, rows_export)

            filtros = f"Ano={ano or '-'} | Modalidade={modalidade or '-'} | Etapa={etapa or '-'} | Série={serie or '-'} | Busca={q or '-'}"
            return export_pdf_table(
                request,
                filename="turmas.pdf",
                title="Relatório — Turmas",
                headers=headers_export,
                rows=rows_export,
                filtros=filtros,
            )

        return super().get(request, *args, **kwargs)

    def get_actions(self, q: str = "", ano=None, **kwargs):
        base_params = []
        if q:
            base_params.append(f"q={escape(q)}")
        if ano:
            base_params.append(f"ano={ano}")
        modalidade = (self.request.GET.get("modalidade") or "").strip()
        etapa = (self.request.GET.get("etapa") or "").strip()
        serie = (self.request.GET.get("serie") or "").strip()
        if modalidade:
            base_params.append(f"modalidade={modalidade}")
        if etapa:
            base_params.append(f"etapa={etapa}")
        if serie:
            base_params.append(f"serie={serie}")
        base_qs = "&".join(base_params)

        actions = [
            {
                "label": "Exportar CSV",
                "url": f"?{base_qs + ('&' if base_qs else '')}export=csv",
                "icon": "fa-solid fa-file-csv",
                "variant": "btn--ghost",
            },
            {
                "label": "Exportar PDF",
                "url": f"?{base_qs + ('&' if base_qs else '')}export=pdf",
                "icon": "fa-solid fa-file-pdf",
                "variant": "btn--ghost",
            },
        ]

        if can(self.request.user, "educacao.manage") or is_admin(self.request.user):
            actions.append({
                "label": "Gerar Turmas em Lote",
                "url": reverse("educacao:turma_geracao_lote"),
                "icon": "fa-solid fa-wand-magic-sparkles",
                "variant": "btn--outline",
            })
            actions.append({
                "label": "Nova Turma",
                "url": reverse("educacao:turma_create"),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            })
        return actions

    def get_headers(self, **kwargs):
        return [
            {"label": "Turma"},
            {"label": "Ano", "width": "110px"},
            {"label": "Turno", "width": "140px"},
            {"label": "Modalidade"},
            {"label": "Etapa"},
            {"label": "Série/Ano"},
            {"label": "Matriz"},
            {"label": "Atividade Extra"},
            {"label": "Unidade"},
            {"label": "Secretaria"},
            {"label": "Município"},
            {"label": "Ativo", "width": "110px"},
        ]

    def get_rows(self, objs, **kwargs):
        can_edit_global = bool(can(self.request.user, "educacao.manage") or is_admin(self.request.user))
        rows = []
        for t in objs:
            unidade = getattr(t, "unidade", None)
            secretaria = getattr(unidade, "secretaria", None) if unidade else None
            municipio = getattr(secretaria, "municipio", None) if secretaria else None

            ativo = getattr(t, "ativo", False)
            ativo_html = '<span class="badge badge--success">Sim</span>' if ativo else '<span class="badge badge--muted">Não</span>'

            rows.append({
                "cells": [
                    {"text": t.nome, "url": reverse("educacao:turma_detail", args=[t.pk])},
                    {"text": str(getattr(t, "ano_letivo", "—"))},
                    {"text": t.get_turno_display() if hasattr(t, "get_turno_display") else (getattr(t, "turno", "") or "—")},
                    {"text": t.get_modalidade_display() if hasattr(t, "get_modalidade_display") else (getattr(t, "modalidade", "") or "—")},
                    {"text": t.get_etapa_display() if hasattr(t, "get_etapa_display") else (getattr(t, "etapa", "") or "—")},
                    {"text": t.get_serie_ano_display() if hasattr(t, "get_serie_ano_display") else (getattr(t, "serie_ano", "") or "—")},
                    {"text": getattr(getattr(t, "matriz_curricular", None), "nome", "—")},
                    {"text": getattr(getattr(t, "curso", None), "nome", "—")},
                    {"text": getattr(unidade, "nome", "—")},
                    {"text": getattr(secretaria, "nome", "—")},
                    {"text": getattr(municipio, "nome", "—")},
                    {"html": ativo_html, "safe": True},
                ],
                "can_edit": can_edit_global,
                "edit_url": reverse("educacao:turma_update", args=[t.pk]) if can_edit_global else "",
            })
        return rows

    def get_extra_filters_html(self, *, q: str = "", ano=None, **kwargs) -> str:
        # anos disponíveis (limitado) dentro do escopo
        qs = self.get_base_queryset()
        anos = list(qs.order_by("-ano_letivo").values_list("ano_letivo", flat=True).distinct())[:12]
        modalidade = (self.request.GET.get("modalidade") or "").strip()
        etapa = (self.request.GET.get("etapa") or "").strip()
        serie = (self.request.GET.get("serie") or "").strip()

        modalidade_choices = self._ensure_selected_choice(
            Turma.modalidades_motor_principal_choices(),
            modalidade,
            Turma.Modalidade.choices,
        )
        etapa_choices = self._ensure_selected_choice(
            Turma.etapas_motor_principal_choices(),
            etapa,
            Turma.Etapa.choices,
        )
        serie_choices = self._ensure_selected_choice(
            Turma.series_motor_principal_choices(),
            serie,
            Turma.SerieAno.choices,
        )

        modalidades_opts = [
            format_html(
                '<option value=""{}>{}</option>',
                " selected" if not modalidade else "",
                "Todas modalidades",
            )
        ]
        modalidades_opts.extend(
            format_html(
                '<option value="{}"{}>{}</option>',
                value,
                " selected" if modalidade == value else "",
                label,
            )
            for value, label in modalidade_choices
        )
        modalidades_html = format_html_join("", "{}", ((item,) for item in modalidades_opts))

        etapas_opts = [
            format_html(
                '<option value=""{}>{}</option>',
                " selected" if not etapa else "",
                "Todas etapas",
            )
        ]
        etapas_opts.extend(
            format_html(
                '<option value="{}"{}>{}</option>',
                value,
                " selected" if etapa == value else "",
                label,
            )
            for value, label in etapa_choices
        )
        etapas_html = format_html_join("", "{}", ((item,) for item in etapas_opts))

        series_opts = [
            format_html(
                '<option value=""{}>{}</option>',
                " selected" if not serie else "",
                "Todas séries/anos",
            )
        ]
        series_opts.extend(
            format_html(
                '<option value="{}"{}>{}</option>',
                value,
                " selected" if serie == value else "",
                label,
            )
            for value, label in serie_choices
        )
        series_html = format_html_join("", "{}", ((item,) for item in series_opts))

        if not anos:
            return str(
                format_html(
                    (
                        '<div class="filter-bar__field"><label class="small">Modalidade</label><select name="modalidade">{}</select></div>'
                        '<div class="filter-bar__field"><label class="small">Etapa</label><select name="etapa">{}</select></div>'
                        '<div class="filter-bar__field"><label class="small">Série/Ano</label><select name="serie">{}</select></div>'
                    ),
                    modalidades_html,
                    etapas_html,
                    series_html,
                )
            )

        ano_opts = [format_html('<option value=""{}>{}</option>', " selected" if not ano else "", "Todos os anos")]
        ano_opts.extend(
            format_html('<option value="{}"{}>{}</option>', a, " selected" if str(ano) == str(a) else "", a)
            for a in anos
        )
        anos_html = format_html_join("", "{}", ((item,) for item in ano_opts))

        return str(
            format_html(
                (
                    '<div class="filter-bar__field"><label class="small">Ano letivo</label><select name="ano">{}</select></div>'
                    '<div class="filter-bar__field"><label class="small">Modalidade</label><select name="modalidade">{}</select></div>'
                    '<div class="filter-bar__field"><label class="small">Etapa</label><select name="etapa">{}</select></div>'
                    '<div class="filter-bar__field"><label class="small">Série/Ano</label><select name="serie">{}</select></div>'
                ),
                anos_html,
                modalidades_html,
                etapas_html,
                series_html,
            )
        )
