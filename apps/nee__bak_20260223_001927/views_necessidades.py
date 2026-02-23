from __future__ import annotations


from apps.core.exports import export_csv, export_pdf_table
from django.http import HttpResponse

from django.db.models import Q
from django.urls import reverse
from django.utils.html import escape
from django.shortcuts import get_object_or_404

from apps.core.rbac import can, scope_filter_alunos
from apps.core.views_gepub import (
    BaseCreateViewGepub,
    BaseDetailViewGepub,
    BaseListViewGepub,
    BaseUpdateViewGepub,
)
from apps.educacao.models import Aluno

from .forms import AlunoNecessidadeForm
from .models import AlunoNecessidade

# ================================
# LIST
# ================================

class AlunoNecessidadeListView(BaseListViewGepub):
    template_name = "nee/aluno_necessidade_list.html"
    paginate_by = 20
    manage_perm = "nee.manage"

    def get_base_queryset(self):
        aluno_id = int(self.kwargs["aluno_id"])
        qs_aluno = scope_filter_alunos(self.request.user, Aluno.objects.filter(id=aluno_id))
        aluno = qs_aluno.first()
        if not aluno:
            return AlunoNecessidade.objects.none()
        self._aluno = aluno
        return (
            AlunoNecessidade.objects
            .select_related("tipo")
            .filter(aluno_id=aluno_id)
            .order_by("-criado_em", "-id")
        )

    def apply_search(self, qs, q: str, **kwargs):
        if q:
            qs = qs.filter(
                Q(tipo__nome__icontains=q)
                | Q(cid__icontains=q)
                | Q(observacao__icontains=q)
            )
        return qs


    def get(self, request, *args, **kwargs):
        """Suporta exportação CSV/PDF sem travar o navegador.

        Usa `?export=csv` ou `?export=pdf` e respeita o filtro de busca `q`.
        """
        export = request.GET.get("export")
        if export in {"csv", "pdf"}:
            aluno_id = int(self.kwargs["aluno_id"])
            aluno = getattr(self, "_aluno", None)
            if not aluno:
                # garante aluno para nomear arquivo e validar escopo
                qs_aluno = scope_filter_alunos(request.user, Aluno.objects.filter(id=aluno_id))
                aluno = qs_aluno.first()
                if not aluno:
                    return HttpResponse("Aluno não encontrado.", status=404)

            q = (request.GET.get("q") or "").strip()
            qs = self.get_base_queryset()
            qs = self.apply_search(qs, q)

            # monta linhas (sem paginação)
            rows = []
            for n in qs:
                rows.append([
                    n.tipo.nome if n.tipo_id else "",
                    n.cid or "",
                    "Sim" if n.ativo else "Não",
                    n.criado_em.strftime("%d/%m/%Y %H:%M") if n.criado_em else "",
                    (n.observacao or "").replace("\n", " ").strip(),
                ])

            headers = ["Tipo", "CID", "Ativo", "Criado em", "Observação"]
            safe_name = f"necessidades_aluno_{aluno_id}"

            if export == "csv":
                return export_csv(
                    request,
                    filename=f"{safe_name}.csv",
                    title=f"NEE — Necessidades ({aluno.nome})",
                    headers=headers,
                    rows=rows,
                    subtitle="Necessidades do aluno",
                    filtros=(f"Busca: {q}" if q else ""),
                )

            # export == "pdf"
            return export_pdf_table(
                request,
                filename=f"{safe_name}.pdf",
                title=f"NEE — Necessidades ({aluno.nome})",
                headers=headers,
                rows=rows,
                subtitle="Necessidades do aluno",
                filtros=(f"Busca: {q}" if q else ""),
            )

        return super().get(request, *args, **kwargs)

    def get_actions(self, q: str = "", **kwargs):
        aluno = getattr(self, "_aluno", None)
        actions = [
            {"label": "Voltar", "url": reverse("nee:aluno_hub", args=[aluno.pk]) if aluno else reverse("nee:buscar_aluno"),
             "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        ]

        if aluno:
            actions.append({
                "label": "Abrir aluno",
                "url": reverse("educacao:aluno_detail", args=[aluno.pk]),
                "icon": "fa-solid fa-user",
                "variant": "btn--ghost",
            })

        if can(self.request.user, "nee.manage") and aluno:
            actions.append({
                "label": "Nova necessidade",
                "url": reverse("nee:necessidade_create", args=[aluno.pk]),
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
            {"label": "Tipo"},
            {"label": "CID", "width": "140px"},
            {"label": "Ativo", "width": "120px"},
            {"label": "Criado", "width": "140px"},
        ]

    def get_rows(self, request, page_obj):
        rows = []
        for n in page_obj.object_list:
            rows.append({
                "cells": [
                    {"text": n.tipo.nome,
                     "url": reverse("nee:necessidade_detail", args=[n.pk])},
                    {"text": n.cid or "—"},
                    {"text": "Sim" if n.ativo else "Não"},
                    {"text": n.criado_em.strftime("%d/%m/%Y") if n.criado_em else "—"},
                ],
                "can_edit": can(request.user, "nee.manage"),
                "edit_url": reverse("nee:necessidade_update", args=[n.pk]),
            })
        return rows


# ================================
# CREATE (AQUI ERA O BUG)
# ================================

class AlunoNecessidadeCreateView(BaseCreateViewGepub):
    template_name = "nee/aluno_necessidade_form.html"
    form_class = AlunoNecessidadeForm
    title = "Nova necessidade"
    subtitle = "Vincular tipo ao aluno"
    manage_perm = "nee.manage"

    # 👇 CORRETO PARA BaseCreateViewGepub
    def form_valid(self, *args, **kwargs):
        """Compat com BaseViewGepub.

        O core pode chamar form_valid(form) (padrão Django) ou form_valid(request, form).
        Aqui detectamos a assinatura em tempo de execução e garantimos que 'form' é o objeto correto.
        """
        # Detecta se veio (request, form)
        if len(args) >= 2 and hasattr(args[0], "method") and hasattr(args[1], "save"):
            request, form = args[0], args[1]
            call_args = (request, form)
        else:
            form = args[0] if args else kwargs.get("form")
            call_args = (form,)

        aluno_id = self.kwargs.get("aluno_id")
        form.instance.aluno = get_object_or_404(Aluno, pk=aluno_id)
        return super().form_valid(*call_args, **kwargs)

    def get_actions(self, q: str = "", **kwargs):
        aluno_id = int(self.kwargs["aluno_id"])
        return [{
            "label": "Voltar",
            "url": reverse("nee:aluno_necessidades", args=[aluno_id]),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }]

    def get_success_url(self, request, obj=None):
        return reverse("nee:aluno_necessidades", args=[obj.aluno_id])


# ================================
# UPDATE
# ================================

class AlunoNecessidadeUpdateView(BaseUpdateViewGepub):
    template_name = "nee/aluno_necessidade_form.html"
    form_class = AlunoNecessidadeForm
    model = AlunoNecessidade
    title = "Editar necessidade"
    subtitle = "Atualizar vínculo do aluno"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        return [{
            "label": "Voltar",
            "url": reverse("nee:necessidade_detail", args=[obj.pk]),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }]

    def get_success_url(self, request, obj=None):
        return reverse("nee:aluno_necessidades", args=[obj.aluno_id])


# ================================
# DETAIL
# ================================

class AlunoNecessidadeDetailView(BaseDetailViewGepub):
    template_name = "nee/aluno_necessidade_detail.html"
    model = AlunoNecessidade
    title = "Necessidade"
    subtitle = "Detalhes do vínculo"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        actions = [
            {"label": "Voltar",
             "url": reverse("nee:aluno_necessidades", args=[obj.aluno_id]),
             "icon": "fa-solid fa-arrow-left",
             "variant": "btn--ghost"},

            {"label": "Abrir aluno",
             "url": reverse("educacao:aluno_detail", args=[obj.aluno_id]),
             "icon": "fa-solid fa-user",
             "variant": "btn--ghost"},
        ]

        if can(self.request.user, "nee.manage"):
            actions.append({
                "label": "Editar",
                "url": reverse("nee:necessidade_update", args=[obj.pk]),
                "icon": "fa-solid fa-pen",
                "variant": "btn-primary",
            })

        return actions

    def get_fields(self, request, obj):
        return [
            ("Aluno", str(obj.aluno)),
            ("Tipo", obj.tipo.nome),
            ("CID", obj.cid or "—"),
            ("Ativo", "Sim" if obj.ativo else "Não"),
            ("Criado em",
             obj.criado_em.strftime("%d/%m/%Y %H:%M") if obj.criado_em else "—"),
            ("Observação", obj.observacao or "—"),
        ]
