from __future__ import annotations

from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models import Prefetch
from django.db.models import Q
from django.http import HttpRequest, JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.text import slugify

from apps.core.rbac import can
from apps.org.forms import SecretariaForm
from apps.org.models import (
    Address,
    Municipio,
    Secretaria,
    SecretariaModuloAtivo,
    SecretariaTemplate,
    Setor,
    Unidade,
)
from apps.org.services.addresses_access import can_edit_entity_address, can_view_coordinates
from apps.org.views_onboarding import TEMPLATE_VISUALS

from apps.core.views_gepub import BaseListViewGepub, BaseCreateViewGepub, BaseUpdateViewGepub, BaseDetailViewGepub
from .views_common import ensure_municipio_scope_or_403, force_user_municipio_id


DEFAULT_SECRETARIA_ICON = "fa-solid fa-building-columns"

_MODEL_KEY_ALIASES = {
    "assistencia_social": SecretariaTemplate.Modulo.ASSISTENCIA,
    "cultura_turismo_esporte": SecretariaTemplate.Modulo.CULTURA,
    "desenvolvimento_economico": SecretariaTemplate.Modulo.DESENVOLVIMENTO,
    "habitacao_urbanismo": SecretariaTemplate.Modulo.HABITACAO,
    "transporte_mobilidade": SecretariaTemplate.Modulo.TRANSPORTE,
}

_MODULO_ATIVO_ALIASES = {
    "administracao": SecretariaTemplate.Modulo.ADMINISTRACAO,
    "educacao": SecretariaTemplate.Modulo.EDUCACAO,
    "saude": SecretariaTemplate.Modulo.SAUDE,
    "obras": SecretariaTemplate.Modulo.OBRAS,
    "agricultura": SecretariaTemplate.Modulo.AGRICULTURA,
    "tecnologia": SecretariaTemplate.Modulo.TECNOLOGIA,
    "assistencia": SecretariaTemplate.Modulo.ASSISTENCIA,
    "meio_ambiente": SecretariaTemplate.Modulo.MEIO_AMBIENTE,
    "transporte": SecretariaTemplate.Modulo.TRANSPORTE,
    "cultura": SecretariaTemplate.Modulo.CULTURA,
    "desenvolvimento": SecretariaTemplate.Modulo.DESENVOLVIMENTO,
    "habitacao": SecretariaTemplate.Modulo.HABITACAO,
    "servicos_publicos": SecretariaTemplate.Modulo.SERVICOS_PUBLICOS,
    "planejamento": SecretariaTemplate.Modulo.PLANEJAMENTO,
    "financeiro": SecretariaTemplate.Modulo.FINANCAS,
    "tributos": SecretariaTemplate.Modulo.FINANCAS,
}

_TEXT_HINTS = (
    (SecretariaTemplate.Modulo.EDUCACAO, ("educacao", "ensino", "escolar", "escola", "semed", "seduc")),
    (SecretariaTemplate.Modulo.SAUDE, ("saude", "clinica", "hospital", "ubs", "sus", "semsa", "sesau", "semus")),
    (SecretariaTemplate.Modulo.ASSISTENCIA, ("assistencia", "assistencial", "social", "semas", "cras", "creas")),
    (SecretariaTemplate.Modulo.FINANCAS, ("financa", "fazenda", "tesouro", "tribut", "arrecad", "sefaz", "semfaz")),
    (SecretariaTemplate.Modulo.OBRAS, ("obras", "engenharia", "infraestrutura", "infra", "urbanismo", "semob")),
    (SecretariaTemplate.Modulo.AGRICULTURA, ("agricultura", "agro", "rural", "campo", "semagri")),
    (SecretariaTemplate.Modulo.MEIO_AMBIENTE, ("meio ambiente", "ambiental", "sustent", "saneamento", "semma")),
    (SecretariaTemplate.Modulo.TRANSPORTE, ("transporte", "mobilidade", "transito", "trafego", "semtrans")),
    (SecretariaTemplate.Modulo.CULTURA, ("cultura", "turismo", "esporte", "lazer", "semcult")),
    (SecretariaTemplate.Modulo.DESENVOLVIMENTO, ("desenvolvimento", "economico", "industria", "comercio", "semdec")),
    (SecretariaTemplate.Modulo.HABITACAO, ("habitacao", "moradia", "regularizacao", "sehab")),
    (SecretariaTemplate.Modulo.TECNOLOGIA, ("tecnologia", "inovacao", "digital", "informatica", "ti", "setic")),
    (SecretariaTemplate.Modulo.PLANEJAMENTO, ("planejamento", "controle interno", "estrategia", "seplan")),
    (SecretariaTemplate.Modulo.SERVICOS_PUBLICOS, ("servicos publicos", "zeladoria", "limpeza urbana", "iluminacao publica")),
    (SecretariaTemplate.Modulo.ADMINISTRACAO, ("administracao", "gestao", "governo", "gabinete", "semad")),
)

_VALID_TEMPLATE_MODULES = {str(key).strip().lower() for key in TEMPLATE_VISUALS.keys() if key}


def _normalize_identifier(value: str) -> str:
    normalized = slugify((value or "").strip())
    return normalized.replace("-", "_")


def _resolve_model_key(value: str) -> str:
    key = _normalize_identifier(value)
    if not key:
        return ""
    if key in _VALID_TEMPLATE_MODULES:
        return key
    resolved = _MODEL_KEY_ALIASES.get(key, "")
    return str(resolved) if resolved else ""


def _matches_hint(normalized_text: str, tokens: set[str], hint: str) -> bool:
    hint_normalized = slugify(hint).replace("-", " ").strip()
    if not hint_normalized:
        return False
    if " " in hint_normalized:
        return hint_normalized in normalized_text
    if len(hint_normalized) <= 3:
        return hint_normalized in tokens
    return any(token.startswith(hint_normalized) for token in tokens)


def _infer_secretaria_module(secretaria: Secretaria) -> str:
    by_modelo = _resolve_model_key(secretaria.tipo_modelo)
    if by_modelo:
        return by_modelo

    modulos_ativos = []
    for mod in secretaria.modulos_ativos.all():
        key = _normalize_identifier(mod.modulo)
        if key and key not in modulos_ativos:
            modulos_ativos.append(key)
    for key in modulos_ativos:
        resolved = _MODULO_ATIVO_ALIASES.get(key)
        if resolved:
            return str(resolved)

    normalized_text = slugify(f"{secretaria.nome} {secretaria.sigla}").replace("-", " ")
    tokens = {token for token in normalized_text.split(" ") if token}
    for module, hints in _TEXT_HINTS:
        if any(_matches_hint(normalized_text, tokens, hint) for hint in hints):
            return str(module)
    return ""


def _secretaria_icon(secretaria: Secretaria) -> str:
    modulo = _infer_secretaria_module(secretaria)
    if not modulo:
        return DEFAULT_SECRETARIA_ICON
    visual = TEMPLATE_VISUALS.get(modulo) or TEMPLATE_VISUALS.get(SecretariaTemplate.Modulo.OUTRO) or {}
    return visual.get("icon") or DEFAULT_SECRETARIA_ICON


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


class SecretariaListView(BaseListViewGepub):
    template_name = "org/secretaria_list.html"
    title = "Secretarias"
    subtitle = "Lista de secretarias por município"
    back_url_name = "org:index"
    paginate_by = 10

    def get_filter_placeholder(self) -> str:
        return "Nome, sigla ou município..."

    def get_queryset(self, request):
        municipio_id = force_user_municipio_id(request.user, (request.GET.get("municipio") or "").strip())

        qs = (
            Secretaria.objects.select_related("municipio")
            .prefetch_related(
                Prefetch(
                    "modulos_ativos",
                    queryset=SecretariaModuloAtivo.objects.filter(ativo=True).only("secretaria_id", "modulo"),
                )
            )
            .annotate(
                qtd_unidades=Count("unidades", distinct=True),
                qtd_setores=Count("unidades__setores", distinct=True),
                qtd_perfis=Count("profiles", distinct=True),
            )
            .all()
        )
        if municipio_id.isdigit():
            qs = qs.filter(municipio_id=int(municipio_id))
        return qs.order_by("nome")

    def apply_search(self, qs, q: str):
        return qs.filter(Q(nome__icontains=q) | Q(sigla__icontains=q) | Q(municipio__nome__icontains=q))

    def get_extra_filters_html(self, request: HttpRequest, **kwargs) -> str:
        municipio_id = force_user_municipio_id(request.user, (request.GET.get("municipio") or "").strip())
        return _municipio_select_html(municipio_id)

    def get_input_attrs(self, request: HttpRequest, **kwargs) -> str:
        return str(
            format_html(
                'data-autocomplete-url="{}" data-autocomplete-href="{}"',
                reverse("org:secretaria_autocomplete"),
                reverse("org:secretaria_list") + "?q={q}",
            )
        )

    def get_actions(self, request, **kwargs):
        actions = super().get_actions(**kwargs)
        if can(request.user, "org.manage_secretaria"):
            actions.insert(0, {"label": "Nova secretaria", "url": reverse("org:secretaria_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})
        return actions

    def get(self, request: HttpRequest, *args, **kwargs):
        self.request = request
        q = (request.GET.get(self.search_param) or "").strip()

        qs = self.get_queryset(request)
        if q:
            qs = self.apply_search(qs, q, **kwargs)

        paginator = Paginator(qs, self.paginate_by)
        page_obj = paginator.get_page(request.GET.get("page"))

        total = qs.count()
        ativos = qs.filter(ativo=True).count()
        inativos = max(0, total - ativos)
        municipios = qs.values("municipio_id").distinct().count()
        unidades_total = sum(int(getattr(item, "qtd_unidades", 0) or 0) for item in page_obj.object_list)

        context = {
            "title": self.title,
            "subtitle": "Visualize, organize e instale secretarias de forma guiada.",
            "actions": self.get_actions(request, q=q, **kwargs),
            "q": q,
            "action_url": request.path,
            "clear_url": request.path,
            "has_filters": bool(q),
            "placeholder": self.get_filter_placeholder(),
            "extra_filters": self.get_extra_filters_html(request, q=q, **kwargs),
            "input_attrs": self.get_input_attrs(request, q=q, **kwargs),
            "headers": self.get_headers(request),
            "rows": self.get_rows(request, page_obj),
            "page_obj": page_obj,
            "summary": {
                "total": total,
                "ativos": ativos,
                "inativos": inativos,
                "municipios": municipios,
                "unidades_pagina": unidades_total,
            },
            "onboarding_url": reverse("org:onboarding_primeiro_acesso"),
            "onboarding_painel_url": reverse("org:onboarding_painel"),
        }
        return render(request, self.template_name, context)

    def get_headers(self, request):
        return [
            {"label": "Nome"},
            {"label": "Sigla", "width": "120px"},
            {"label": "Município"},
            {"label": "Ativo", "width": "90px"},
        ]

    def get_rows(self, request, page_obj):
        rows = []
        can_edit = bool(can(request.user, "org.manage_secretaria"))
        can_manage_secretaria = bool(can(request.user, "org.manage_secretaria"))
        for s in page_obj.object_list:
            ativo_html = (
                f'<span class="status {"success" if s.ativo else "danger"}">'
                f'{"Sim" if s.ativo else "Não"}'
                f"</span>"
            )
            rows.append({
                "id": s.pk,
                "nome": s.nome,
                "sigla": s.sigla or "—",
                "icon": _secretaria_icon(s),
                "municipio": f"{s.municipio.nome}/{s.municipio.uf}",
                "ativo": bool(s.ativo),
                "qtd_unidades": int(getattr(s, "qtd_unidades", 0) or 0),
                "qtd_setores": int(getattr(s, "qtd_setores", 0) or 0),
                "qtd_perfis": int(getattr(s, "qtd_perfis", 0) or 0),
                "detail_url": reverse("org:secretaria_detail", args=[s.pk]),
                "governanca_url": reverse("org:secretaria_governanca_detail", args=[s.pk]) if can_manage_secretaria else "",
                "cells": [
                    {"text": s.nome, "url": reverse("org:secretaria_detail", args=[s.pk])},
                    {"text": s.sigla or "—"},
                    {"text": f"{s.municipio.nome}/{s.municipio.uf}"},
                    {"html": ativo_html, "safe": True},
                ],
                "can_edit": can_edit,
                "edit_url": reverse("org:secretaria_update", args=[s.pk]) if can_edit else "",
            })
        return rows


class SecretariaCreateView(BaseCreateViewGepub):
    title = "Nova secretaria"
    subtitle = "Cadastre uma secretaria vinculada a um município"
    back_url_name = "org:secretaria_list"
    form_class = SecretariaForm
    submit_label = "Salvar secretaria"

    def dispatch(self, request, *args, **kwargs):
        if not can(request.user, "org.manage_secretaria"):
            return HttpResponseForbidden("403 — Você não possui permissão para criar secretaria.")
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, request: HttpRequest, *args, **kwargs):
        return self.form_class(*args, user=request.user, **kwargs)

    def form_valid(self, request: HttpRequest, form):
        # Política comercial atual: secretarias sem limite por plano.
        return super().form_valid(request, form)

    def get_success_url(self, request, obj=None) -> str:
        return reverse("org:secretaria_detail", args=[obj.pk])


class SecretariaUpdateView(BaseUpdateViewGepub):
    title = "Editar secretaria"
    subtitle = "Atualize os dados da secretaria"
    back_url_name = "org:secretaria_list"
    form_class = SecretariaForm
    model = Secretaria
    submit_label = "Atualizar secretaria"

    def dispatch(self, request, *args, **kwargs):
        if not can(request.user, "org.manage_secretaria"):
            return HttpResponseForbidden("403 — Você não possui permissão para editar secretaria.")

        pk = kwargs.get("pk")
        if pk:
            secretaria = Secretaria.objects.filter(pk=pk).select_related("municipio").only("id", "municipio_id").first()
            if secretaria:
                block = ensure_municipio_scope_or_403(request.user, secretaria.municipio_id)
                if block:
                    return block
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, request: HttpRequest, *args, **kwargs):
        return self.form_class(*args, user=request.user, **kwargs)

    def get_success_url(self, request, obj=None) -> str:
        return reverse("org:secretaria_detail", args=[obj.pk])


class SecretariaDetailView(BaseDetailViewGepub):
    title = "Secretaria"
    subtitle = "Detalhes e vínculos"
    back_url_name = "org:secretaria_list"
    model = Secretaria
    template_name = "org/secretaria_detail.html"

    def get(self, request, pk: int, *args, **kwargs):
        secretaria = get_object_or_404(Secretaria.objects.select_related("municipio"), pk=pk)
        block = ensure_municipio_scope_or_403(request.user, secretaria.municipio_id)
        if block:
            return block

        unidades_qs = Unidade.objects.filter(secretaria_id=secretaria.id)
        setores_qs = Setor.objects.filter(unidade__secretaria_id=secretaria.id)

        actions = [{"label": "Voltar", "url": reverse("org:secretaria_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
        if can(request.user, "org.manage_secretaria"):
            actions.append({"label": "Editar", "url": reverse("org:secretaria_update", args=[secretaria.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})

        fields = [
            {"label": "Nome", "value": secretaria.nome},
            {"label": "Sigla", "value": secretaria.sigla or "—"},
            {"label": "Município", "value": f"{secretaria.municipio.nome}/{secretaria.municipio.uf}"},
            {"label": "Ativo", "value": "Sim" if secretaria.ativo else "Não"},
        ]

        pills = [
            {"label": "Unidades", "value": unidades_qs.count()},
            {"label": "Setores", "value": setores_qs.count()},
        ]

        location_qs = Address.objects.filter(
            entity_type=Address.EntityType.SECRETARIA,
            entity_id=secretaria.id,
            is_active=True,
        ).order_by("-is_primary", "id")
        principal_address = location_qs.first()
        can_edit_location = can_edit_entity_address(request.user, Address.EntityType.SECRETARIA, secretaria.id)
        show_coords = can_view_coordinates(request.user, Address.EntityType.SECRETARIA, secretaria.id)

        links = [
            {
                "label": "Ver unidades",
                "url": reverse("org:unidade_list") + f"?municipio={secretaria.municipio_id}",
                "meta": f"{unidades_qs.count()} registros",
                "icon": "fa-solid fa-school",
            },
            {
                "label": "Ver setores",
                "url": reverse("org:setor_list"),
                "meta": f"{setores_qs.count()} registros",
                "icon": "fa-solid fa-sitemap",
            },
        ]
        if can(request.user, "org.manage_secretaria"):
            links.insert(
                0,
                {
                    "label": "Governança da secretaria",
                    "url": reverse("org:secretaria_governanca_detail", args=[secretaria.pk]),
                    "meta": "Configurações e cadastros-base",
                    "icon": "fa-solid fa-sliders",
                },
            )

        return render(request, self.template_name, {
            "title": secretaria.nome,
            "subtitle": "Detalhes e vínculos",
            "actions": actions,
            "obj": secretaria,
            "fields": fields,
            "pills": pills,
            "links": links,
            "location_entity_type": Address.EntityType.SECRETARIA,
            "location_entity_id": secretaria.id,
            "location_address": principal_address,
            "location_can_edit": can_edit_location,
            "location_show_coordinates": show_coords,
        })


def secretaria_autocomplete(request: HttpRequest):
    q = (request.GET.get("q") or "").strip()
    municipio_id = force_user_municipio_id(request.user, (request.GET.get("municipio") or "").strip())

    qs = Secretaria.objects.select_related("municipio").all()
    if municipio_id.isdigit():
        qs = qs.filter(municipio_id=int(municipio_id))
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(sigla__icontains=q) | Q(municipio__nome__icontains=q))

    items = list(qs.order_by("nome")[:20].values("id", "nome", "sigla"))
    return JsonResponse({"results": [{"id": it["id"], "text": it["nome"]} for it in items]})
