from __future__ import annotations

from urllib.parse import urlencode

from django.db.models import Q
from django.http import HttpRequest, JsonResponse, HttpResponseForbidden, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from apps.core.rbac import can, scope_filter_municipios, scope_filter_secretarias, scope_filter_unidades
from apps.org.forms import LocalEstruturalForm
from apps.org.models import LocalEstrutural, Municipio, Secretaria, Unidade

from apps.core.views_gepub import BaseListViewGepub, BaseCreateViewGepub, BaseUpdateViewGepub, BaseDetailViewGepub
from .views_common import ensure_municipio_scope_or_403, force_user_municipio_id


def _municipio_select_html(municipios, selected: str) -> str:
    opts = [format_html('<option value="">{}</option>', "Todos os municípios")]
    for m in municipios:
        sel = " selected" if selected and str(m.id) == str(selected) else ""
        opts.append(format_html('<option value="{}"{}>{}/{}</option>', m.id, sel, m.nome, m.uf))
    options_html = format_html_join("", "{}", ((item,) for item in opts))
    return str(
        format_html(
            '<div class="filter-bar__field"><label class="small">Município</label><select name="municipio">{}</select></div>',
            options_html,
        )
    )


def _secretaria_select_html(secretarias, selected: str) -> str:
    opts = [format_html('<option value="">{}</option>', "Todas as secretarias")]
    for s in secretarias:
        sel = " selected" if selected and str(s.id) == str(selected) else ""
        opts.append(format_html('<option value="{}"{}>{}</option>', s.id, sel, s.nome))
    options_html = format_html_join("", "{}", ((item,) for item in opts))
    return str(
        format_html(
            '<div class="filter-bar__field"><label class="small">Secretaria</label><select name="secretaria">{}</select></div>',
            options_html,
        )
    )


def _unidade_select_html(unidades, selected: str) -> str:
    opts = [format_html('<option value="">{}</option>', "Todas as unidades")]
    for u in unidades:
        sel = " selected" if selected and str(u.id) == str(selected) else ""
        opts.append(format_html('<option value="{}"{}>{}</option>', u.id, sel, u.nome))
    options_html = format_html_join("", "{}", ((item,) for item in opts))
    return str(
        format_html(
            '<div class="filter-bar__field"><label class="small">Unidade</label><select name="unidade">{}</select></div>',
            options_html,
        )
    )


def _tipo_local_select_html(selected: str) -> str:
    opts = [format_html('<option value="">{}</option>', "Todos os tipos")]
    for value, label in LocalEstrutural.TipoLocal.choices:
        sel = " selected" if selected == value else ""
        opts.append(format_html('<option value="{}"{}>{}</option>', value, sel, label))
    options_html = format_html_join("", "{}", ((item,) for item in opts))
    return str(
        format_html(
            '<div class="filter-bar__field"><label class="small">Tipo</label><select name="tipo_local">{}</select></div>',
            options_html,
        )
    )


def _nome_hierarquico(local: LocalEstrutural) -> str:
    prefixo = "-- " * int(getattr(local, "nivel", 0) or 0)
    return f"{prefixo}{local.nome}"


class LocalEstruturalListView(BaseListViewGepub):
    title = "Locais Estruturais"
    subtitle = "Estrutura física hierárquica por secretaria e unidade"
    back_url_name = "org:index"
    paginate_by = 15

    def get_filter_placeholder(self) -> str:
        return "Nome, código, responsável, unidade ou secretaria..."

    def get_queryset(self, request):
        municipio_id = force_user_municipio_id(request.user, (request.GET.get("municipio") or "").strip())
        secretaria_id = (request.GET.get("secretaria") or "").strip()
        unidade_id = (request.GET.get("unidade") or "").strip()
        tipo_local = (request.GET.get("tipo_local") or "").strip().upper()

        unidades_scope = scope_filter_unidades(request.user, Unidade.objects.all())

        qs = LocalEstrutural.objects.select_related(
            "municipio",
            "secretaria",
            "unidade",
            "local_pai",
        ).filter(unidade_id__in=unidades_scope.values_list("id", flat=True))

        if municipio_id.isdigit():
            qs = qs.filter(municipio_id=int(municipio_id))
        if secretaria_id.isdigit():
            qs = qs.filter(secretaria_id=int(secretaria_id))
        if unidade_id.isdigit():
            qs = qs.filter(unidade_id=int(unidade_id))
        if tipo_local and tipo_local in dict(LocalEstrutural.TipoLocal.choices):
            qs = qs.filter(tipo_local=tipo_local)

        return qs.order_by("unidade__nome", "local_pai_id", "nome")

    def apply_search(self, qs, q: str):
        return qs.filter(
            Q(nome__icontains=q)
            | Q(codigo__icontains=q)
            | Q(responsavel__icontains=q)
            | Q(unidade__nome__icontains=q)
            | Q(secretaria__nome__icontains=q)
            | Q(municipio__nome__icontains=q)
        )

    def get_extra_filters_html(self, request: HttpRequest, **kwargs) -> str:
        municipio_id = force_user_municipio_id(request.user, (request.GET.get("municipio") or "").strip())
        secretaria_id = (request.GET.get("secretaria") or "").strip()
        unidade_id = (request.GET.get("unidade") or "").strip()
        tipo_local = (request.GET.get("tipo_local") or "").strip().upper()

        municipios = scope_filter_municipios(request.user, Municipio.objects.filter(ativo=True).order_by("nome"))
        secretarias = scope_filter_secretarias(
            request.user,
            Secretaria.objects.filter(ativo=True).select_related("municipio").order_by("nome"),
        )
        unidades = scope_filter_unidades(
            request.user,
            Unidade.objects.filter(ativo=True).select_related("secretaria", "secretaria__municipio").order_by("nome"),
        )

        if municipio_id.isdigit():
            secretarias = secretarias.filter(municipio_id=int(municipio_id))
            unidades = unidades.filter(secretaria__municipio_id=int(municipio_id))
        if secretaria_id.isdigit():
            unidades = unidades.filter(secretaria_id=int(secretaria_id))

        return "".join(
            [
                _municipio_select_html(municipios, municipio_id),
                _secretaria_select_html(secretarias, secretaria_id),
                _unidade_select_html(unidades, unidade_id),
                _tipo_local_select_html(tipo_local),
            ]
        )

    def get_input_attrs(self, request: HttpRequest, **kwargs) -> str:
        params: dict[str, str] = {}
        for key in ("municipio", "secretaria", "unidade", "tipo_local"):
            value = (request.GET.get(key) or "").strip()
            if value:
                params[key] = value
        params["q"] = "{q}"
        href = reverse("org:local_estrutural_list") + "?" + urlencode(params)
        return str(
            format_html(
                'data-autocomplete-url="{}" data-autocomplete-href="{}"',
                reverse("org:local_estrutural_autocomplete"),
                href,
            )
        )

    def get_actions(self, request, **kwargs):
        actions = super().get_actions(**kwargs)
        if can(request.user, "org.manage_unidade"):
            actions.insert(
                0,
                {
                    "label": "Novo local",
                    "url": reverse("org:local_estrutural_create"),
                    "icon": "fa-solid fa-plus",
                    "variant": "gp-button--primary",
                },
            )
        actions.append(
            {
                "label": "CSV",
                "url": request.get_full_path() + ("&" if "?" in request.get_full_path() else "?") + "export=csv",
                "icon": "fa-solid fa-file-csv",
                "variant": "gp-button--ghost",
            }
        )
        actions.append(
            {
                "label": "PDF",
                "url": request.get_full_path() + ("&" if "?" in request.get_full_path() else "?") + "export=pdf",
                "icon": "fa-solid fa-file-pdf",
                "variant": "gp-button--ghost",
            }
        )
        return actions

    def get_headers(self, request):
        return [
            {"label": "Local"},
            {"label": "Tipo", "width": "170px"},
            {"label": "Unidade"},
            {"label": "Secretaria"},
            {"label": "Município"},
            {"label": "Status", "width": "100px"},
        ]

    def get_rows(self, request, page_obj):
        rows = []
        can_edit = bool(can(request.user, "org.manage_unidade"))
        for local in page_obj.object_list:
            status_html = (
                f'<span class="status {"success" if local.status == LocalEstrutural.Status.ATIVO else "danger"}">'
                f'{"Ativo" if local.status == LocalEstrutural.Status.ATIVO else "Inativo"}'
                "</span>"
            )
            rows.append(
                {
                    "cells": [
                        {
                            "text": _nome_hierarquico(local),
                            "url": reverse("org:local_estrutural_detail", args=[local.pk]),
                        },
                        {"text": local.get_tipo_local_display()},
                        {"text": local.unidade.nome if local.unidade else "—"},
                        {"text": local.secretaria.nome if local.secretaria else "—"},
                        {"text": f"{local.municipio.nome}/{local.municipio.uf}" if local.municipio else "—"},
                        {"html": status_html, "safe": True},
                    ],
                    "can_edit": can_edit,
                    "edit_url": reverse("org:local_estrutural_update", args=[local.pk]) if can_edit else "",
                }
            )
        return rows

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        export = (request.GET.get("export") or "").strip().lower()
        if export in ("csv", "pdf"):
            from apps.core.exports import export_csv, export_pdf_table

            qs = self.get_queryset(request)
            q = (request.GET.get("q") or "").strip()
            if q:
                qs = self.apply_search(qs, q)
            items = list(qs[:500])
            headers = [
                "Local",
                "Tipo",
                "Unidade",
                "Secretaria",
                "Município",
                "Código",
                "Responsável",
                "Status",
            ]
            rows = [
                [
                    obj.caminho,
                    obj.get_tipo_local_display(),
                    obj.unidade.nome if obj.unidade else "",
                    obj.secretaria.nome if obj.secretaria else "",
                    f"{obj.municipio.nome}/{obj.municipio.uf}" if obj.municipio else "",
                    obj.codigo or "",
                    obj.responsavel or "",
                    obj.get_status_display(),
                ]
                for obj in items
            ]
            if export == "csv":
                return export_csv("locais_estruturais.csv", headers, rows)
            municipio_label = (request.GET.get("municipio") or "").strip() or "todos"
            return export_pdf_table(
                request,
                filename="locais_estruturais.pdf",
                title="Locais estruturais",
                subtitle=f"Filtro município: {municipio_label}",
                headers=headers,
                rows=rows,
                filtros=f"Busca={q or '-'}",
            )
        return super().get(request, *args, **kwargs)


class LocalEstruturalCreateView(BaseCreateViewGepub):
    title = "Novo local estrutural"
    subtitle = "Cadastre um local interno hierárquico"
    back_url_name = "org:local_estrutural_list"
    form_class = LocalEstruturalForm
    submit_label = "Salvar local"
    template_name = "org/local_estrutural_form.html"

    def dispatch(self, request, *args, **kwargs):
        if not can(request.user, "org.manage_unidade"):
            return HttpResponseForbidden("403 — Você não possui permissão para criar local estrutural.")
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, request: HttpRequest, *args, **kwargs):
        return self.form_class(*args, user=request.user, **kwargs)

    def get_success_url(self, request, obj=None) -> str:
        return reverse("org:local_estrutural_detail", args=[obj.pk])


class LocalEstruturalUpdateView(BaseUpdateViewGepub):
    title = "Editar local estrutural"
    subtitle = "Atualize os dados do local"
    back_url_name = "org:local_estrutural_list"
    form_class = LocalEstruturalForm
    model = LocalEstrutural
    submit_label = "Editar local"
    template_name = "org/local_estrutural_form.html"

    def dispatch(self, request, *args, **kwargs):
        if not can(request.user, "org.manage_unidade"):
            return HttpResponseForbidden("403 — Você não possui permissão para editar local estrutural.")

        pk = kwargs.get("pk")
        if pk:
            local = LocalEstrutural.objects.select_related("municipio").filter(pk=pk).only("id", "municipio_id").first()
            block = ensure_municipio_scope_or_403(request.user, getattr(local, "municipio_id", None))
            if block:
                return block
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, request: HttpRequest, *args, **kwargs):
        return self.form_class(*args, user=request.user, **kwargs)

    def get_success_url(self, request, obj=None) -> str:
        return reverse("org:local_estrutural_detail", args=[obj.pk])


class LocalEstruturalDetailView(BaseDetailViewGepub):
    title = "Local estrutural"
    subtitle = "Detalhes"
    back_url_name = "org:local_estrutural_list"
    model = LocalEstrutural
    template_name = "org/local_estrutural_detail.html"

    def get(self, request, pk: int, *args, **kwargs):
        local = get_object_or_404(
            LocalEstrutural.objects.select_related("municipio", "secretaria", "unidade", "local_pai"),
            pk=pk,
        )
        block = ensure_municipio_scope_or_403(request.user, local.municipio_id)
        if block:
            return block

        filhos_qs = LocalEstrutural.objects.filter(local_pai_id=local.id)

        actions = [{"label": "Voltar", "url": reverse("org:local_estrutural_list"), "icon": "fa-solid fa-arrow-left", "variant": "gp-button--ghost"}]
        if can(request.user, "org.manage_unidade"):
            actions.append(
                {
                    "label": "Editar",
                    "url": reverse("org:local_estrutural_update", args=[local.pk]),
                    "icon": "fa-solid fa-pen",
                    "variant": "gp-button--primary",
                }
            )

        fields = [
            {"label": "Nome", "value": local.nome},
            {"label": "Caminho", "value": local.caminho},
            {"label": "Tipo", "value": local.get_tipo_local_display()},
            {"label": "Código", "value": local.codigo or "—"},
            {"label": "Responsável", "value": local.responsavel or "—"},
            {"label": "Unidade", "value": local.unidade.nome if local.unidade else "—"},
            {"label": "Secretaria", "value": local.secretaria.nome if local.secretaria else "—"},
            {"label": "Município", "value": f"{local.municipio.nome}/{local.municipio.uf}" if local.municipio else "—"},
            {"label": "Status", "value": local.get_status_display()},
            {"label": "Observações", "value": local.observacoes or "—"},
        ]

        return render(
            request,
            self.template_name,
            {
                "title": local.nome,
                "subtitle": "Detalhes",
                "actions": actions,
                "obj": local,
                "fields": fields,
                "pills": [
                    {"label": "Nível", "value": local.nivel},
                    {"label": "Filhos diretos", "value": filhos_qs.count()},
                ],
                "links": [
                    {
                        "label": "Visualizar unidade",
                        "url": reverse("org:unidade_detail", args=[local.unidade_id]),
                        "meta": local.unidade.nome if local.unidade else "—",
                        "icon": "fa-solid fa-school",
                    },
                    {
                        "label": "Visualizar local pai",
                        "url": reverse("org:local_estrutural_detail", args=[local.local_pai_id])
                        if local.local_pai_id
                        else reverse("org:local_estrutural_list"),
                        "meta": local.local_pai.nome if local.local_pai else "Sem local pai",
                        "icon": "fa-solid fa-sitemap",
                    },
                    {
                        "label": "Visualizar sublocais",
                        "url": reverse("org:local_estrutural_list") + f"?unidade={local.unidade_id}",
                        "meta": f"{filhos_qs.count()} sublocal(is)",
                        "icon": "fa-solid fa-folder-tree",
                    },
                ],
            },
        )


def local_estrutural_autocomplete(request: HttpRequest):
    q = (request.GET.get("q") or "").strip()
    unidade_id = (request.GET.get("unidade") or "").strip()

    unidades_scope = scope_filter_unidades(request.user, Unidade.objects.all())
    qs = LocalEstrutural.objects.filter(unidade_id__in=unidades_scope.values_list("id", flat=True))

    if unidade_id.isdigit():
        qs = qs.filter(unidade_id=int(unidade_id))

    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(codigo__icontains=q) | Q(unidade__nome__icontains=q))

    items = list(qs.order_by("nome")[:20].values("id", "nome", "codigo"))
    return JsonResponse(
        {
            "results": [
                {
                    "id": it["id"],
                    "text": f"{it['nome']} ({it['codigo']})" if it.get("codigo") else it["nome"],
                }
                for it in items
            ]
        }
    )
