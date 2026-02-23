from __future__ import annotations

from django.db.models import Q
from django.urls import reverse
from django.utils.html import escape

from apps.core.rbac import can
from apps.core.exports import export_csv, export_pdf_table

from .base_views import BaseAlunoListView, BaseAlunoCreateView, BaseAlunoUpdateView, BaseAlunoDetailView
from .forms import AcompanhamentoNEEForm
from .models import AcompanhamentoNEE


class AcompanhamentoListView(BaseAlunoListView):
    template_name = "nee/acompanhamento_list.html"
    paginate_by = 20
    manage_perm = "nee.manage"

    def get_base_queryset(self):
        aluno = self.get_aluno()
        return AcompanhamentoNEE.objects.filter(aluno=aluno).order_by("-data", "-id")

    def apply_search(self, qs, q: str, **kwargs):
        if q:
            qs = qs.filter(Q(descricao__icontains=q) | Q(tipo_evento__icontains=q))
        return qs

    def get_actions(self, q: str = "", **kwargs):
        actions = super().get_actions(q=q, **kwargs)

        aluno = self.get_aluno()
        if can(self.request.user, "nee.manage"):
            actions.append({
                "label": "Novo acompanhamento",
                "url": reverse("nee:acompanhamento_create", args=[aluno.pk]),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            })

        actions.append({
            "label": "Exportar CSV",
            "url": f"{self.request.path}?q={escape(q)}&export=csv",
            "icon": "fa-solid fa-file-csv",
            "variant": "btn--ghost",
        })
        actions.append({
            "label": "Exportar PDF",
            "url": f"{self.request.path}?q={escape(q)}&export=pdf",
            "icon": "fa-solid fa-file-pdf",
            "variant": "btn--ghost",
        })
        return actions

    def get_headers(self, *args, **kwargs):
        return [
            {"label": "Data", "width": "140px"},
            {"label": "Tipo", "width": "200px"},
            {"label": "Visibilidade", "width": "200px"},
            {"label": "Descrição"},
        ]

    def get_rows(self, request, page_obj):
        rows = []
        for a in page_obj.object_list:
            rows.append({
                "cells": [
                    {"text": a.data.strftime("%d/%m/%Y") if a.data else "—", "url": reverse("nee:acompanhamento_detail", args=[a.pk])},
                    {"text": a.get_tipo_evento_display()},
                    {"text": a.get_visibilidade_display()},
                    {"text": (a.descricao[:110] + "…") if a.descricao and len(a.descricao) > 110 else (a.descricao or "—")},
                ],
                "can_edit": can(request.user, "nee.manage"),
                "edit_url": reverse("nee:acompanhamento_update", args=[a.pk]),
            })
        return rows

    def get(self, request, *args, **kwargs):
        q = (request.GET.get(self.search_param) or "").strip()
        export = request.GET.get("export")
        if export in ("csv", "pdf"):
            qs = self.get_queryset(request)
            if q:
                qs = self.apply_search(qs, q)

            headers = ["Data", "Tipo", "Visibilidade", "Descrição"]
            rows = [[
                (a.data.strftime("%d/%m/%Y") if a.data else ""),
                a.get_tipo_evento_display(),
                a.get_visibilidade_display(),
                a.descricao or "",
            ] for a in qs]

            aluno = self.get_aluno()
            if export == "csv":
                return export_csv(f"nee_acompanhamentos_{aluno.pk}.csv", headers, rows)

            return export_pdf_table(
                request,
                filename=f"nee_acompanhamentos_{aluno.pk}.pdf",
                title=f"NEE — Acompanhamentos ({aluno.nome})",
                subtitle="Linha do tempo / acompanhamentos",
                headers=headers,
                rows=rows,
                filtros=(f"Busca: {q}" if q else ""),
            )

        return super().get(request, *args, **kwargs)


class AcompanhamentoCreateView(BaseAlunoCreateView):
    template_name = "nee/acompanhamento_form.html"
    form_class = AcompanhamentoNEEForm
    title = "Novo acompanhamento"
    subtitle = "Registrar evento/observação"
    manage_perm = "nee.manage"

    back_url_name = "nee:aluno_acompanhamentos"
    success_url_name = "nee:aluno_acompanhamentos"


class AcompanhamentoUpdateView(BaseAlunoUpdateView):
    template_name = "nee/acompanhamento_form.html"
    form_class = AcompanhamentoNEEForm
    model = AcompanhamentoNEE
    title = "Editar acompanhamento"
    subtitle = "Atualizar registro"
    manage_perm = "nee.manage"

    success_url_name = "nee:aluno_acompanhamentos"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        return [{
            "label": "Voltar",
            "url": reverse("nee:acompanhamento_detail", args=[obj.pk]),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }]


class AcompanhamentoDetailView(BaseAlunoDetailView):
    template_name = "nee/acompanhamento_detail.html"
    model = AcompanhamentoNEE
    title = "Acompanhamento"
    subtitle = "Detalhes do registro"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        actions = [
            {
                "label": "Voltar",
                "url": reverse("nee:aluno_acompanhamentos", args=[obj.aluno_id]),
                "icon": "fa-solid fa-arrow-left",
                "variant": "btn--ghost",
            },
            {
                "label": "Abrir aluno",
                "url": reverse("educacao:aluno_detail", args=[obj.aluno_id]),
                "icon": "fa-solid fa-user",
                "variant": "btn--ghost",
            },
        ]
        if can(self.request.user, "nee.manage"):
            actions.append({
                "label": "Editar",
                "url": reverse("nee:acompanhamento_update", args=[obj.pk]),
                "icon": "fa-solid fa-pen",
                "variant": "btn-primary",
            })
        return actions

    def get_fields(self, request, obj):
        return [
            ("Aluno", str(obj.aluno)),
            ("Data", obj.data.strftime("%d/%m/%Y") if obj.data else "—"),
            ("Tipo", obj.get_tipo_evento_display()),
            ("Visibilidade", obj.get_visibilidade_display()),
            ("Autor", str(obj.autor) if getattr(obj, "autor_id", None) else "—"),
            ("Descrição", obj.descricao or "—"),
        ]
