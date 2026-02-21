from __future__ import annotations

from django.db.models import Q
from django.http import HttpRequest, JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from apps.core.rbac import get_profile, is_admin
from apps.org.forms import SecretariaForm
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


class SecretariaListView(BaseListViewGepub):
    title = "Secretarias"
    subtitle = "Lista de secretarias por município"
    back_url_name = "org:index"
    paginate_by = 10

    def get_filter_placeholder(self) -> str:
        return "Nome, sigla ou município..."

    def get_queryset(self, request):
        municipio_id = force_user_municipio_id(request.user, (request.GET.get("municipio") or "").strip())

        qs = Secretaria.objects.select_related("municipio").all()
        if municipio_id.isdigit():
            qs = qs.filter(municipio_id=int(municipio_id))
        return qs.order_by("nome")

    def apply_search(self, qs, q: str):
        return qs.filter(Q(nome__icontains=q) | Q(sigla__icontains=q) | Q(municipio__nome__icontains=q))

    def get_extra_filters_html(self, request: HttpRequest, **kwargs) -> str:
        municipio_id = force_user_municipio_id(request.user, (request.GET.get("municipio") or "").strip())
        return _municipio_select_html(municipio_id)

    def get_input_attrs(self, request: HttpRequest, **kwargs) -> str:
        return 'data-autocomplete-url="%s" data-autocomplete-href="%s"' % (
            reverse("org:secretaria_autocomplete"),
            reverse("org:secretaria_list") + "?q={q}",
        )

    def get_actions(self, request, **kwargs):
        actions = super().get_actions(request, **kwargs)
        if is_admin(request.user):
            actions.insert(0, {"label": "Nova secretaria", "url": reverse("org:secretaria_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})
        return actions

    def get_headers(self, request):
        return [
            {"label": "Nome"},
            {"label": "Sigla", "width": "120px"},
            {"label": "Município"},
            {"label": "Ativo", "width": "90px"},
        ]

    def get_rows(self, request, page_obj):
        rows = []
        can_edit = bool(is_admin(request.user))
        for s in page_obj.object_list:
            ativo_html = (
                f'<span class="status {"success" if s.ativo else "danger"}">'
                f'{"Sim" if s.ativo else "Não"}'
                f"</span>"
            )
            rows.append({
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
        if not is_admin(request.user):
            return HttpResponseForbidden("403 — Apenas administrador pode criar secretaria.")
        return super().dispatch(request, *args, **kwargs)

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
        if not is_admin(request.user):
            return HttpResponseForbidden("403 — Apenas administrador pode editar secretaria.")
        return super().dispatch(request, *args, **kwargs)

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
        if is_admin(request.user):
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

        return render(request, self.template_name, {
            "title": secretaria.nome,
            "subtitle": "Detalhes e vínculos",
            "actions": actions,
            "obj": secretaria,
            "fields": fields,
            "pills": pills,
            "links": [
                {"label": "Ver unidades", "url": reverse("org:unidade_list") + f"?municipio={secretaria.municipio_id}", "meta": f"{unidades_qs.count()}"},
                {"label": "Ver setores", "url": reverse("org:setor_list"), "meta": f"{setores_qs.count()}"},
            ]
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
