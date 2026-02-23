from __future__ import annotations

from datetime import date, timedelta

from django.contrib import messages
from django.db.models import Q, Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import escape

from apps.core.rbac import can
from apps.core.views_gepub import BaseCreateViewGepub, BaseDetailViewGepub, BaseListViewGepub, BaseUpdateViewGepub
from apps.core.exports import export_csv, export_pdf_table

from apps.educacao.models import Aluno

from .forms import PlanoClinicoNEEForm, ObjetivoPlanoNEEForm, EvolucaoPlanoNEEForm
from .models import PlanoClinicoNEE, ObjetivoPlanoNEE, EvolucaoPlanoNEE, LaudoNEE
from .utils import get_scoped_aluno


# ============================================================
# HUB CLÍNICO DO ALUNO
# ============================================================

def aluno_hub(request: HttpRequest, aluno_id: int) -> HttpResponse:
    aluno = get_scoped_aluno(request.user, int(aluno_id))

    # plano (auto-cria)
    plano, _created = PlanoClinicoNEE.objects.get_or_create(
        aluno=aluno,
        defaults={"responsavel": request.user},
    )
    # Se o plano existir e estiver sem responsável (caso de migração manual)
    if plano.responsavel_id is None:
        plano.responsavel = request.user
        plano.save(update_fields=["responsavel"])

    # alertas: laudos vencidos / vencendo
    today = date.today()
    soon = today + timedelta(days=30)
    laudos_qs = LaudoNEE.objects.filter(aluno=aluno).order_by("-data_emissao", "-id")
    laudos_vencidos = laudos_qs.filter(validade__isnull=False, validade__lt=today).count()
    laudos_vencendo = laudos_qs.filter(validade__isnull=False, validade__gte=today, validade__lte=soon).count()

    # contagens rápidas
    counts = {
        "necessidades": getattr(aluno, "necessidadesnee", None).all().count() if hasattr(aluno, "necessidadesnee") else 0,
        "laudos": laudos_qs.count(),
        "recursos": getattr(aluno, "recursosnee", None).all().count() if hasattr(aluno, "recursosnee") else 0,
        "apoios": getattr(aluno, "apoiosnee", None).all().count() if hasattr(aluno, "apoiosnee") else 0,
        "acompanhamentos": getattr(aluno, "acompanhamentosnee", None).all().count() if hasattr(aluno, "acompanhamentosnee") else 0,
        "objetivos": plano.objetivos.all().count(),
    }

    alerts = []
    if laudos_vencidos:
        alerts.append({"variant": "badge--danger", "label": "Laudos vencidos", "value": laudos_vencidos})
    if laudos_vencendo:
        alerts.append({"variant": "badge--warning", "label": "Laudos vencendo (30d)", "value": laudos_vencendo})

    actions = [
        {"label": "Voltar", "url": reverse("nee:buscar_aluno"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Relatório PDF", "url": reverse("nee:aluno_relatorio_clinico_pdf", args=[aluno.pk]), "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]

    ctx = {
        "aluno": aluno,
        "plano": plano,
        "counts": counts,
        "alerts": alerts,
        "actions": actions,
        "page_title": "Hub Clínico",
        "page_subtitle": "Plano clínico-pedagógico NEE",
        "can_manage": can(request.user, "nee.manage"),
        "links": {
            "necessidades": reverse("nee:aluno_necessidades", args=[aluno.pk]),
            "laudos": reverse("nee:aluno_laudos", args=[aluno.pk]),
            "recursos": reverse("nee:aluno_recursos", args=[aluno.pk]),
            "apoios": reverse("nee:aluno_apoios", args=[aluno.pk]),
            "acompanhamentos": reverse("nee:aluno_acompanhamentos", args=[aluno.pk]),
            "timeline": reverse("nee:aluno_timeline", args=[aluno.pk]),
            "plano": reverse("nee:aluno_plano_clinico", args=[aluno.pk]),
            "objetivos": reverse("nee:aluno_objetivos", args=[aluno.pk]),
        },
    }
    return render(request, "nee/aluno_hub.html", ctx)


# ============================================================
# PLANO CLÍNICO (editar direto pelo aluno_id)
# ============================================================

def aluno_plano_clinico(request: HttpRequest, aluno_id: int) -> HttpResponse:
    aluno = get_scoped_aluno(request.user, int(aluno_id))
    plano, _ = PlanoClinicoNEE.objects.get_or_create(aluno=aluno, defaults={"responsavel": request.user})

    if request.method == "POST":
        form = PlanoClinicoNEEForm(request.POST, instance=plano)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.responsavel_id is None:
                obj.responsavel = request.user
            obj.save()
            messages.success(request, "Plano clínico atualizado com sucesso.")
            return redirect("nee:aluno_hub", aluno_id=aluno.pk)
    else:
        form = PlanoClinicoNEEForm(instance=plano)

    actions = [{"label": "Voltar", "url": reverse("nee:aluno_hub", args=[aluno.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    ctx = {"aluno": aluno, "form": form, "title": "Plano Clínico", "subtitle": aluno.nome, "actions": actions}
    return render(request, "nee/plano_form.html", ctx)


# ============================================================
# OBJETIVOS (list / create / update / detail)
# ============================================================

class ObjetivoListView(BaseListViewGepub):
    template_name = "nee/objetivo_list.html"
    paginate_by = 20
    manage_perm = "nee.manage"

    def get_base_queryset(self):
        aluno = get_scoped_aluno(self.request.user, int(self.kwargs["aluno_id"]))
        self._aluno = aluno
        plano, _ = PlanoClinicoNEE.objects.get_or_create(aluno=aluno, defaults={"responsavel": self.request.user})
        self._plano = plano
        return ObjetivoPlanoNEE.objects.filter(plano=plano).order_by("-criado_em", "-id")

    def apply_search(self, qs, q: str, **kwargs):
        if q:
            qs = qs.filter(Q(descricao__icontains=q) | Q(meta__icontains=q) | Q(area__icontains=q) | Q(status__icontains=q))
        return qs

    def get(self, request, *args, **kwargs):
        export = request.GET.get("export")
        if export in {"csv", "pdf"}:
            q = (request.GET.get("q") or "").strip()
            qs = self.get_base_queryset()
            qs = self.apply_search(qs, q)

            headers = ["Área", "Descrição", "Meta", "Prazo", "Status", "Criado em"]
            rows = []
            for o in qs:
                rows.append([
                    o.get_area_display(),
                    o.descricao,
                    o.meta or "",
                    o.prazo.strftime("%d/%m/%Y") if o.prazo else "",
                    o.get_status_display(),
                    o.criado_em.strftime("%d/%m/%Y %H:%M") if o.criado_em else "",
                ])

            aluno = getattr(self, "_aluno", None)
            safe = f"objetivos_aluno_{aluno.pk if aluno else 'x'}"

            if export == "csv":
                return export_csv(f"{safe}.csv", headers, rows)
            return export_pdf_table(
                request,
                filename=f"{safe}.pdf",
                title=f"NEE — Objetivos ({aluno.nome if aluno else ''})",
                headers=headers,
                rows=rows,
                subtitle="Objetivos terapêuticos",
                filtros=(f"Busca: {q}" if q else ""),
            )
        return super().get(request, *args, **kwargs)

    def get_actions(self, q: str = "", **kwargs):
        aluno = getattr(self, "_aluno", None)
        actions = [{"label": "Voltar", "url": reverse("nee:aluno_hub", args=[aluno.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
        if can(self.request.user, "nee.manage") and aluno:
            actions.append({"label": "Novo objetivo", "url": reverse("nee:objetivo_create", args=[aluno.pk]), "icon": "fa-solid fa-plus", "variant": "btn-primary"})
        actions.append({"label": "Exportar CSV", "url": f"{self.request.path}?q={escape(q)}&export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"})
        actions.append({"label": "Exportar PDF", "url": f"{self.request.path}?q={escape(q)}&export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"})
        return actions

    def get_headers(self, *args, **kwargs):
        return [{"label": "Área"}, {"label": "Descrição"}, {"label": "Status", "width": "160px"}]

    def get_rows(self, request, page_obj):
        rows = []
        for o in page_obj.object_list:
            rows.append({
                "cells": [
                    {"text": o.get_area_display()},
                    {"text": o.descricao, "url": reverse("nee:objetivo_detail", args=[o.pk])},
                    {"text": o.get_status_display()},
                ],
                "can_edit": can(request.user, "nee.manage"),
                "edit_url": reverse("nee:objetivo_update", args=[o.pk]),
            })
        return rows


class ObjetivoCreateView(BaseCreateViewGepub):
    template_name = "nee/objetivo_form.html"
    form_class = ObjetivoPlanoNEEForm
    title = "Novo objetivo"
    subtitle = "Cadastrar objetivo terapêutico"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", **kwargs):
        aluno_id = int(self.kwargs["aluno_id"])
        return [{"label": "Voltar", "url": reverse("nee:aluno_objetivos", args=[aluno_id]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]

    def form_valid(self, request, form):
        aluno = get_scoped_aluno(request.user, int(self.kwargs["aluno_id"]))
        plano, _ = PlanoClinicoNEE.objects.get_or_create(aluno=aluno, defaults={"responsavel": request.user})
        form.instance.plano = plano
        return super().form_valid(request, form)

    def get_success_url(self, request, obj=None):
        return reverse("nee:aluno_objetivos", args=[obj.plano.aluno_id])


class ObjetivoUpdateView(BaseUpdateViewGepub):
    template_name = "nee/objetivo_form.html"
    form_class = ObjetivoPlanoNEEForm
    model = ObjetivoPlanoNEE
    title = "Editar objetivo"
    subtitle = "Atualizar objetivo terapêutico"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        return [{"label": "Voltar", "url": reverse("nee:objetivo_detail", args=[obj.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]

    def get_success_url(self, request, obj=None):
        return reverse("nee:aluno_objetivos", args=[obj.plano.aluno_id])


class ObjetivoDetailView(BaseDetailViewGepub):
    template_name = "nee/objetivo_detail.html"
    model = ObjetivoPlanoNEE
    title = "Objetivo"
    subtitle = "Detalhes do objetivo"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", obj=None, **kwargs):
        actions = [{"label": "Voltar", "url": reverse("nee:aluno_objetivos", args=[obj.plano.aluno_id]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
        if can(self.request.user, "nee.manage"):
            actions.append({"label": "Editar", "url": reverse("nee:objetivo_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})
            actions.append({"label": "Nova evolução", "url": reverse("nee:evolucao_create", args=[obj.pk]), "icon": "fa-solid fa-plus", "variant": "btn--ghost"})
        return actions

    def get_fields(self, request, obj):
        return [
            ("Área", obj.get_area_display()),
            ("Descrição", obj.descricao),
            ("Meta", obj.meta or "—"),
            ("Prazo", obj.prazo.strftime("%d/%m/%Y") if obj.prazo else "—"),
            ("Status", obj.get_status_display()),
            ("Criado em", obj.criado_em.strftime("%d/%m/%Y %H:%M") if obj.criado_em else "—"),
        ]


# ============================================================
# EVOLUÇÕES (create / list by objetivo)
# ============================================================

class EvolucaoCreateView(BaseCreateViewGepub):
    template_name = "nee/evolucao_form.html"
    form_class = EvolucaoPlanoNEEForm
    title = "Nova evolução"
    subtitle = "Registrar evolução"
    manage_perm = "nee.manage"

    def get_actions(self, q: str = "", **kwargs):
        objetivo_id = int(self.kwargs["objetivo_id"])
        return [{"label": "Voltar", "url": reverse("nee:objetivo_detail", args=[objetivo_id]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]

    def form_valid(self, request, form):
        objetivo = get_object_or_404(ObjetivoPlanoNEE, pk=int(self.kwargs["objetivo_id"]))
        form.instance.objetivo = objetivo
        return super().form_valid(request, form)

    def get_success_url(self, request, obj=None):
        return reverse("nee:objetivo_detail", args=[obj.objetivo_id])
