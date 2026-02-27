from __future__ import annotations

from django.db.models import Q
from django.http import HttpRequest, JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from apps.core.rbac import is_admin
from apps.org.forms import UnidadeForm
from apps.org.models import Municipio, Secretaria, Unidade, Setor

from apps.core.views_gepub import BaseListViewGepub, BaseCreateViewGepub, BaseUpdateViewGepub, BaseDetailViewGepub
from .views_common import ensure_municipio_scope_or_403, force_user_municipio_id


def _municipio_select_html(selected: str) -> str:
    opts = ['<option value="">Todos os municípios</option>']
    for m in Municipio.objects.order_by("nome"):
        sel = ' selected' if selected and str(m.id) == str(selected) else ''
        opts.append(f'<option value="{m.id}"{sel}>{m.nome}/{m.uf}</option>')
    return (
        '<div class="filter-bar__field">'
        '<label class="small">Município</label>'
        f'<select name="municipio">{"".join(opts)}</select>'
        '</div>'
    )


class UnidadeListView(BaseListViewGepub):
    title = "Unidades"
    subtitle = "Lista de unidades por secretaria"
    back_url_name = "org:index"
    paginate_by = 10

    def get_filter_placeholder(self) -> str:
        return "Nome da unidade, secretaria ou município..."

    def get_queryset(self, request):
        municipio_id = force_user_municipio_id(request.user, (request.GET.get("municipio") or "").strip())
        qs = Unidade.objects.select_related("secretaria__municipio").all()
        if municipio_id.isdigit():
            qs = qs.filter(secretaria__municipio_id=int(municipio_id))
        return qs.order_by("nome")

    def apply_search(self, qs, q: str):
        return qs.filter(Q(nome__icontains=q) | Q(secretaria__nome__icontains=q) | Q(secretaria__municipio__nome__icontains=q))

    def get_extra_filters_html(self, request: HttpRequest, **kwargs) -> str:
        municipio_id = force_user_municipio_id(request.user, (request.GET.get("municipio") or "").strip())
        return _municipio_select_html(municipio_id)

    def get_input_attrs(self, request: HttpRequest, **kwargs) -> str:
        return 'data-autocomplete-url="%s" data-autocomplete-href="%s"' % (
            reverse("org:unidade_autocomplete"),
            reverse("org:unidade_list") + "?q={q}",
        )

    def get_actions(self, request, **kwargs):
        actions = super().get_actions(request, **kwargs)
        if is_admin(request.user):
            actions.insert(0, {"label": "Nova unidade", "url": reverse("org:unidade_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})
        return actions

    def get_headers(self, request):
        return [
            {"label": "Nome"},
            {"label": "Secretaria"},
            {"label": "Município"},
            {"label": "Ativo", "width": "90px"},
        ]

    def get_rows(self, request, page_obj):
        rows = []
        can_edit = bool(is_admin(request.user))
        for u in page_obj.object_list:
            municipio = u.secretaria.municipio if u.secretaria else None
            ativo_html = (
                f'<span class="status {"success" if u.ativo else "danger"}">'
                f'{"Sim" if u.ativo else "Não"}'
                f"</span>"
            )
            rows.append({
                "cells": [
                    {"text": u.nome or "—", "url": reverse("org:unidade_detail", args=[u.pk])},
                    {"text": u.secretaria.nome if u.secretaria else "—"},
                    {"text": f"{municipio.nome}/{municipio.uf}" if municipio else "—"},
                    {"html": ativo_html, "safe": True},
                ],
                "can_edit": can_edit,
                "edit_url": reverse("org:unidade_update", args=[u.pk]) if can_edit else "",
            })
        return rows


class UnidadeCreateView(BaseCreateViewGepub):
    title = "Nova unidade"
    subtitle = "Cadastre uma unidade vinculada a uma secretaria"
    back_url_name = "org:unidade_list"
    form_class = UnidadeForm
    submit_label = "Salvar unidade"

    def dispatch(self, request, *args, **kwargs):
        if not is_admin(request.user):
            return HttpResponseForbidden("403 — Apenas administrador pode criar unidade.")
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self, request, obj=None) -> str:
        return reverse("org:unidade_detail", args=[obj.pk])


class UnidadeUpdateView(BaseUpdateViewGepub):
    title = "Editar unidade"
    subtitle = "Atualize os dados da unidade"
    back_url_name = "org:unidade_list"
    form_class = UnidadeForm
    model = Unidade
    submit_label = "Atualizar unidade"

    def dispatch(self, request, *args, **kwargs):
        if not is_admin(request.user):
            return HttpResponseForbidden("403 — Apenas administrador pode editar unidade.")
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self, request, obj=None) -> str:
        return reverse("org:unidade_detail", args=[obj.pk])


class UnidadeDetailView(BaseDetailViewGepub):
    title = "Unidade"
    subtitle = "Detalhes e setores"
    back_url_name = "org:unidade_list"
    model = Unidade
    template_name = "org/unidade_detail.html"

    def get(self, request, pk: int, *args, **kwargs):
        unidade = get_object_or_404(Unidade.objects.select_related("secretaria__municipio"), pk=pk)
        municipio_id = unidade.secretaria.municipio_id if unidade.secretaria else None
        block = ensure_municipio_scope_or_403(request.user, municipio_id)
        if block:
            return block

        setores_qs = Setor.objects.filter(unidade_id=unidade.id)

        actions = [{"label": "Voltar", "url": reverse("org:unidade_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
        if is_admin(request.user):
            actions.append({"label": "Editar", "url": reverse("org:unidade_update", args=[unidade.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})

        municipio = unidade.secretaria.municipio if unidade.secretaria else None

        fields = [
            {"label": "Nome", "value": unidade.nome or "—"},
            {"label": "Tipo", "value": unidade.get_tipo_display() if hasattr(unidade, "get_tipo_display") else (unidade.tipo or "—")},
            {"label": "Secretaria", "value": unidade.secretaria.nome if unidade.secretaria else "—"},
            {"label": "Município", "value": f"{municipio.nome}/{municipio.uf}" if municipio else "—"},
            {"label": "Ativo", "value": "Sim" if unidade.ativo else "Não"},
            {"label": "Código INEP", "value": unidade.codigo_inep or "—"},
            {"label": "CNPJ", "value": unidade.cnpj or "—"},
            {"label": "E-mail", "value": unidade.email or "—"},
            {"label": "Telefone", "value": unidade.telefone or "—"},
        ]

        pills = [
            {"label": "Setores", "value": setores_qs.count()},
        ]

        return render(request, self.template_name, {
            "title": unidade.nome or f"Unidade #{unidade.pk}",
            "subtitle": "Detalhes e setores",
            "actions": actions,
            "obj": unidade,
            "fields": fields,
            "pills": pills,
            "links": [
                {
                    "label": "Ver setores",
                    "url": reverse("org:setor_list") + f"?unidade={unidade.id}",
                    "meta": f"{setores_qs.count()} registros",
                    "icon": "fa-solid fa-sitemap",
                },
            ]
        })


def unidade_autocomplete(request: HttpRequest):
    q = (request.GET.get("q") or "").strip()
    municipio_id = force_user_municipio_id(request.user, (request.GET.get("municipio") or "").strip())

    qs = Unidade.objects.select_related("secretaria__municipio").all()
    if municipio_id.isdigit():
        qs = qs.filter(secretaria__municipio_id=int(municipio_id))
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(secretaria__nome__icontains=q) | Q(secretaria__municipio__nome__icontains=q))

    items = list(qs.order_by("nome")[:20].values("id", "nome"))
    return JsonResponse({"results": [{"id": it["id"], "text": it["nome"]} for it in items]})
