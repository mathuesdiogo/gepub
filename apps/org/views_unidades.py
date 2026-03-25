from __future__ import annotations

from urllib.parse import urlencode

from django.db.models import Q
from django.http import HttpRequest, JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from apps.core.rbac import can
from apps.org.forms import UnidadeForm
from apps.org.models import Address, Municipio, Secretaria, Unidade, Setor
from apps.org.services.addresses_access import can_edit_entity_address, can_view_coordinates

from apps.core.views_gepub import BaseListViewGepub, BaseCreateViewGepub, BaseUpdateViewGepub, BaseDetailViewGepub
from .views_common import ensure_municipio_scope_or_403, force_user_municipio_id


def _municipio_select_html(selected: str) -> str:
    opts = [format_html('<option value="">{}</option>', "Todos os municípios")]
    for m in Municipio.objects.order_by("nome"):
        sel = ' selected' if selected and str(m.id) == str(selected) else ''
        opts.append(format_html('<option value="{}"{}>{}/{}</option>', m.id, sel, m.nome, m.uf))
    options_html = format_html_join("", "{}", ((item,) for item in opts))
    return str(
        format_html(
            '<div class="filter-bar__field"><label class="small">Município</label><select name="municipio">{}</select></div>',
            options_html,
        )
    )


def _tipo_select_html(selected: str) -> str:
    opts = [format_html('<option value="">{}</option>', "Todos os tipos")]
    for value, label in Unidade.Tipo.choices:
        sel = " selected" if selected == value else ""
        opts.append(format_html('<option value="{}"{}>{}</option>', value, sel, label))
    options_html = format_html_join("", "{}", ((item,) for item in opts))
    return str(
        format_html(
            '<div class="filter-bar__field"><label class="small">Tipo</label><select name="tipo">{}</select></div>',
            options_html,
        )
    )


def _tipo_educacional_select_html(selected: str) -> str:
    opts = [format_html('<option value="">{}</option>', "Todas")]
    for value, label in Unidade.TipoEducacional.choices:
        if value == Unidade.TipoEducacional.NAO_APLICA:
            continue
        sel = " selected" if selected == value else ""
        opts.append(format_html('<option value="{}"{}>{}</option>', value, sel, label))
    options_html = format_html_join("", "{}", ((item,) for item in opts))
    return str(
        format_html(
            '<div class="filter-bar__field"><label class="small">Identificação educacional</label><select name="tipo_educacional">{}</select></div>',
            options_html,
        )
    )


class UnidadeListView(BaseListViewGepub):
    title = "Unidades"
    subtitle = "Lista de unidades por secretaria"
    back_url_name = "org:index"
    paginate_by = 10

    def get_filter_placeholder(self) -> str:
        return "Nome da unidade, secretaria, município ou tipo..."

    def get_queryset(self, request):
        municipio_id = force_user_municipio_id(request.user, (request.GET.get("municipio") or "").strip())
        tipo = (request.GET.get("tipo") or "").strip().upper()
        tipo_educacional = (request.GET.get("tipo_educacional") or "").strip().upper()
        qs = Unidade.objects.select_related("secretaria__municipio").all()
        if municipio_id.isdigit():
            qs = qs.filter(secretaria__municipio_id=int(municipio_id))
        if tipo and tipo in dict(Unidade.Tipo.choices):
            qs = qs.filter(tipo=tipo)
        if tipo_educacional and tipo_educacional in dict(Unidade.TipoEducacional.choices):
            qs = qs.filter(tipo_educacional=tipo_educacional)
        return qs.order_by("nome")

    def apply_search(self, qs, q: str):
        return qs.filter(
            Q(nome__icontains=q)
            | Q(secretaria__nome__icontains=q)
            | Q(secretaria__municipio__nome__icontains=q)
            | Q(tipo__icontains=q)
            | Q(tipo_educacional__icontains=q)
        )

    def get_extra_filters_html(self, request: HttpRequest, **kwargs) -> str:
        municipio_id = force_user_municipio_id(request.user, (request.GET.get("municipio") or "").strip())
        tipo = (request.GET.get("tipo") or "").strip().upper()
        tipo_educacional = (request.GET.get("tipo_educacional") or "").strip().upper()
        return "".join(
            [
                _municipio_select_html(municipio_id),
                _tipo_select_html(tipo),
                _tipo_educacional_select_html(tipo_educacional),
            ]
        )

    def get_input_attrs(self, request: HttpRequest, **kwargs) -> str:
        municipio_id = force_user_municipio_id(request.user, (request.GET.get("municipio") or "").strip())
        tipo = (request.GET.get("tipo") or "").strip().upper()
        tipo_educacional = (request.GET.get("tipo_educacional") or "").strip().upper()
        params: dict[str, str] = {}
        if municipio_id:
            params["municipio"] = municipio_id
        if tipo:
            params["tipo"] = tipo
        if tipo_educacional:
            params["tipo_educacional"] = tipo_educacional
        params["q"] = "{q}"
        href = reverse("org:unidade_list") + "?" + urlencode(params)
        return str(
            format_html(
                'data-autocomplete-url="{}" data-autocomplete-href="{}"',
                reverse("org:unidade_autocomplete"),
                href,
            )
        )

    def get_actions(self, request, **kwargs):
        actions = super().get_actions(**kwargs)
        if can(request.user, "org.manage_unidade"):
            create_params: dict[str, str] = {}
            tipo = (request.GET.get("tipo") or "").strip().upper()
            tipo_educacional = (request.GET.get("tipo_educacional") or "").strip().upper()
            if tipo and tipo in dict(Unidade.Tipo.choices):
                create_params["tipo"] = tipo
            if tipo_educacional and tipo_educacional in dict(Unidade.TipoEducacional.choices):
                create_params["tipo_educacional"] = tipo_educacional
            create_url = reverse("org:unidade_create")
            if create_params:
                create_url = f"{create_url}?{urlencode(create_params)}"
            actions.insert(0, {"label": "Nova unidade", "url": create_url, "icon": "fa-solid fa-plus", "variant": "gp-button--primary"})
        return actions

    def get_headers(self, request):
        return [
            {"label": "Nome"},
            {"label": "Tipo", "width": "170px"},
            {"label": "Identificação", "width": "210px"},
            {"label": "Secretaria"},
            {"label": "Município"},
            {"label": "Ativo", "width": "90px"},
        ]

    def get_rows(self, request, page_obj):
        rows = []
        can_edit = bool(can(request.user, "org.manage_unidade"))
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
                    {"text": u.get_tipo_display() if hasattr(u, "get_tipo_display") else (u.tipo or "—")},
                    {
                        "text": (
                            u.get_tipo_educacional_display()
                            if getattr(u, "tipo", "") == Unidade.Tipo.EDUCACAO and hasattr(u, "get_tipo_educacional_display")
                            else "—"
                        )
                    },
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
        if not can(request.user, "org.manage_unidade"):
            return HttpResponseForbidden("403 — Você não possui permissão para criar unidade.")
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, request: HttpRequest, *args, **kwargs):
        initial = dict(kwargs.pop("initial", {}) or {})
        tipo = (request.GET.get("tipo") or "").strip().upper()
        tipo_educacional = (request.GET.get("tipo_educacional") or "").strip().upper()
        if tipo and tipo in dict(Unidade.Tipo.choices):
            initial.setdefault("tipo", tipo)
        if tipo_educacional and tipo_educacional in dict(Unidade.TipoEducacional.choices):
            initial.setdefault("tipo_educacional", tipo_educacional)
        return self.form_class(*args, user=request.user, initial=initial, **kwargs)

    def get_success_url(self, request, obj=None) -> str:
        return reverse("org:unidade_detail", args=[obj.pk])


class UnidadeUpdateView(BaseUpdateViewGepub):
    title = "Editar unidade"
    subtitle = "Atualize os dados da unidade"
    back_url_name = "org:unidade_list"
    form_class = UnidadeForm
    model = Unidade
    submit_label = "Editar unidade"

    def dispatch(self, request, *args, **kwargs):
        if not can(request.user, "org.manage_unidade"):
            return HttpResponseForbidden("403 — Você não possui permissão para editar unidade.")

        pk = kwargs.get("pk")
        if pk:
            unidade = Unidade.objects.select_related("secretaria").filter(pk=pk).only("id", "secretaria__municipio_id").first()
            if unidade and unidade.secretaria_id:
                block = ensure_municipio_scope_or_403(request.user, unidade.secretaria.municipio_id)
                if block:
                    return block
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, request: HttpRequest, *args, **kwargs):
        return self.form_class(*args, user=request.user, **kwargs)

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

        actions = [{"label": "Voltar", "url": reverse("org:unidade_list"), "icon": "fa-solid fa-arrow-left", "variant": "gp-button--ghost"}]
        if can(request.user, "org.manage_unidade"):
            actions.append({"label": "Editar", "url": reverse("org:unidade_update", args=[unidade.pk]), "icon": "fa-solid fa-pen", "variant": "gp-button--primary"})

        municipio = unidade.secretaria.municipio if unidade.secretaria else None

        fields = [
            {"label": "Nome", "value": unidade.nome or "—"},
            {"label": "Tipo", "value": unidade.get_tipo_display() if hasattr(unidade, "get_tipo_display") else (unidade.tipo or "—")},
            {
                "label": "Identificação educacional",
                "value": (
                    unidade.get_tipo_educacional_display()
                    if getattr(unidade, "tipo", "") == Unidade.Tipo.EDUCACAO and hasattr(unidade, "get_tipo_educacional_display")
                    else "—"
                ),
            },
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

        location_qs = Address.objects.filter(
            entity_type=Address.EntityType.UNIDADE,
            entity_id=unidade.id,
            is_active=True,
        ).order_by("-is_primary", "id")
        principal_address = location_qs.first()
        can_edit_location = can_edit_entity_address(request.user, Address.EntityType.UNIDADE, unidade.id)
        show_coords = can_view_coordinates(request.user, Address.EntityType.UNIDADE, unidade.id)

        return render(request, self.template_name, {
            "title": unidade.nome or f"Unidade #{unidade.pk}",
            "subtitle": "Detalhes e setores",
            "actions": actions,
            "obj": unidade,
            "fields": fields,
            "pills": pills,
            "links": [
                {
                    "label": "Visualizar setores",
                    "url": reverse("org:setor_list") + f"?unidade={unidade.id}",
                    "meta": f"{setores_qs.count()} registros",
                    "icon": "fa-solid fa-sitemap",
                },
                {
                    "label": "Visualizar locais estruturais",
                    "url": reverse("org:local_estrutural_list") + f"?unidade={unidade.id}",
                    "meta": "Estrutura interna em árvore",
                    "icon": "fa-solid fa-folder-tree",
                },
            ],
            "location_entity_type": Address.EntityType.UNIDADE,
            "location_entity_id": unidade.id,
            "location_address": principal_address,
            "location_can_edit": can_edit_location,
            "location_show_coordinates": show_coords,
            "legacy_address_text": unidade.endereco or "",
        })


def unidade_autocomplete(request: HttpRequest):
    q = (request.GET.get("q") or "").strip()
    municipio_id = force_user_municipio_id(request.user, (request.GET.get("municipio") or "").strip())
    tipo = (request.GET.get("tipo") or "").strip().upper()
    tipo_educacional = (request.GET.get("tipo_educacional") or "").strip().upper()

    qs = Unidade.objects.select_related("secretaria__municipio").all()
    if municipio_id.isdigit():
        qs = qs.filter(secretaria__municipio_id=int(municipio_id))
    if tipo and tipo in dict(Unidade.Tipo.choices):
        qs = qs.filter(tipo=tipo)
    if tipo_educacional and tipo_educacional in dict(Unidade.TipoEducacional.choices):
        qs = qs.filter(tipo_educacional=tipo_educacional)
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(secretaria__nome__icontains=q) | Q(secretaria__municipio__nome__icontains=q))

    items = list(qs.order_by("nome")[:20].values("id", "nome"))
    return JsonResponse({"results": [{"id": it["id"], "text": it["nome"]} for it in items]})
