from __future__ import annotations

from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse, HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse

from apps.core.rbac import is_admin, scope_filter_municipios
from apps.org.forms import MunicipioForm
from apps.org.models import Municipio, Secretaria, Unidade, Setor

from apps.core.views_gepub import BaseListViewGepub, BaseCreateViewGepub, BaseUpdateViewGepub, BaseDetailViewGepub
from .views_common import ensure_municipio_scope_or_403


class MunicipioListView(BaseListViewGepub):
    title = "Municípios"
    subtitle = "Lista de municípios cadastrados"
    back_url_name = "org:index"
    paginate_by = 10

    def get_filter_placeholder(self) -> str:
        return "Buscar por município ou UF..."

    def get_queryset(self, request):
        return scope_filter_municipios(request.user, Municipio.objects.all()).order_by("nome")

    def apply_search(self, qs, q: str):
        return qs.filter(Q(nome__icontains=q) | Q(uf__icontains=q))

    def get_input_attrs(self, request: HttpRequest, **kwargs) -> str:
        return 'data-autocomplete-url="%s" data-autocomplete-href="%s"' % (
            reverse("org:municipio_autocomplete"),
            reverse("org:municipio_list") + "?q={q}",
        )

    def get_actions(self, request, **kwargs):
        actions = super().get_actions(request, **kwargs)
        if is_admin(request.user):
            actions.insert(0, {"label": "Novo município", "url": reverse("org:municipio_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})
        return actions

    def get_headers(self, request):
        return [
            {"label": "Município"},
            {"label": "UF", "width": "90px"},
            {"label": "Ativo", "width": "90px"},
        ]

    def get_rows(self, request, page_obj):
        rows = []
        can_edit = bool(is_admin(request.user))
        for m in page_obj.object_list:
            ativo_html = (
                f'<span class="status {"success" if m.ativo else "danger"}">'
                f'{"Sim" if m.ativo else "Não"}'
                f"</span>"
            )
            rows.append({
                "cells": [
                    {"text": m.nome, "url": reverse("org:municipio_detail", args=[m.pk])},
                    {"text": m.uf or "—"},
                    {"html": ativo_html, "safe": True},
                ],
                "can_edit": can_edit,
                "edit_url": reverse("org:municipio_update", args=[m.pk]) if can_edit else "",
            })
        return rows


class MunicipioCreateView(BaseCreateViewGepub):
    title = "Novo município"
    subtitle = "Preencha os dados do município e da prefeitura"
    back_url_name = "org:municipio_list"
    form_class = MunicipioForm
    submit_label = "Salvar município"

    def dispatch(self, request, *args, **kwargs):
        if not is_admin(request.user):
            return HttpResponseForbidden("403 — Apenas administrador pode criar município.")
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self, request, obj=None) -> str:
        return reverse("org:municipio_detail", args=[obj.pk])


class MunicipioUpdateView(BaseUpdateViewGepub):
    title = "Editar município"
    subtitle = "Atualize os dados do município"
    back_url_name = "org:municipio_list"
    form_class = MunicipioForm
    model = Municipio
    submit_label = "Atualizar município"

    def dispatch(self, request, *args, **kwargs):
        if not is_admin(request.user):
            return HttpResponseForbidden("403 — Apenas administrador pode editar município.")
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self, request, obj=None) -> str:
        return reverse("org:municipio_detail", args=[obj.pk])


class MunicipioDetailView(BaseDetailViewGepub):
    title = "Município"
    subtitle = "Detalhes e vínculos institucionais"
    back_url_name = "org:municipio_list"
    model = Municipio
    template_name = "org/municipio_detail.html"

    def get(self, request, pk: int, *args, **kwargs):
        municipio = get_object_or_404(Municipio, pk=pk)
        block = ensure_municipio_scope_or_403(request.user, municipio.id)
        if block:
            return block

        secretarias_qs = Secretaria.objects.filter(municipio_id=municipio.id)
        unidades_qs = Unidade.objects.filter(secretaria__municipio_id=municipio.id)
        setores_qs = Setor.objects.filter(unidade__secretaria__municipio_id=municipio.id)

        fields = [
            ("Município", municipio.nome),
            ("UF", municipio.uf),
            ("Ativo", "Sim" if municipio.ativo else "Não"),
            ("Prefeito(a)", municipio.nome_prefeito or "—"),
            ("Telefone", municipio.telefone_prefeitura or "—"),
            ("E-mail", municipio.email_prefeitura or "—"),
            ("Site", municipio.site_prefeitura or "—"),
        ]

        pills = [
            ("Secretarias", secretarias_qs.count()),
            ("Unidades", unidades_qs.count()),
            ("Setores", setores_qs.count()),
        ]

        actions = [{"label": "Voltar", "url": reverse("org:municipio_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
        if is_admin(request.user):
            actions.append({"label": "Editar", "url": reverse("org:municipio_update", args=[municipio.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})

        return render(request, self.template_name, {
            "title": f"{municipio.nome}/{municipio.uf}",
            "subtitle": "Detalhes e vínculos",
            "actions": actions,
            "obj": municipio,
            "fields": [{"label": k, "value": v} for k, v in fields],
            "pills": [{"label": k, "value": v} for k, v in pills],
            "links": [
                {"label": "Ver secretarias", "url": reverse("org:secretaria_list") + f"?municipio={municipio.id}", "meta": f"{secretarias_qs.count()}"},
                {"label": "Ver unidades", "url": reverse("org:unidade_list") + f"?municipio={municipio.id}", "meta": f"{unidades_qs.count()}"},
                {"label": "Ver setores", "url": reverse("org:setor_list") + f"?municipio={municipio.id}", "meta": f"{setores_qs.count()}"},
            ]
        })


def municipio_autocomplete(request: HttpRequest):
    q = (request.GET.get("q") or "").strip()
    qs = scope_filter_municipios(request.user, Municipio.objects.all())
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(uf__icontains=q))
    items = list(qs.order_by("nome")[:20].values("id", "nome", "uf"))
    return JsonResponse({"results": [{"id": it["id"], "text": f'{it["nome"]}/{it["uf"]}'} for it in items]})
