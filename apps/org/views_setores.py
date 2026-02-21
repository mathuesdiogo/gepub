from __future__ import annotations

from django.db.models import Q
from django.http import HttpRequest, JsonResponse, HttpResponseForbidden, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from apps.core.rbac import is_admin, scope_filter_unidades
from apps.org.forms import SetorForm
from apps.org.models import Unidade, Setor

from apps.core.views_gepub import BaseListViewGepub, BaseCreateViewGepub, BaseUpdateViewGepub, BaseDetailViewGepub


def _unidade_select_html(unidades, selected: str) -> str:
    opts = ['<option value="">Todas as unidades</option>']
    for u in unidades:
        sel = ' selected' if selected and str(u.id) == str(selected) else ''
        opts.append(f'<option value="{u.id}"{sel}>{u.nome}</option>')
    return (
        '<div class="filter-bar__field">'
        '<label class="small">Unidade</label>'
        f'<select name="unidade">{"".join(opts)}</select>'
        '</div>'
    )


class SetorListView(BaseListViewGepub):
    title = "Setores"
    subtitle = "Lista de setores por unidade"
    back_url_name = "org:index"
    paginate_by = 10

    def get_filter_placeholder(self) -> str:
        return "Nome do setor, unidade, secretaria ou município..."

    def get_queryset(self, request):
        unidades_scope = scope_filter_unidades(
            request.user,
            Unidade.objects.select_related("secretaria", "secretaria__municipio").all()
        )
        unidade_id = (request.GET.get("unidade") or "").strip()

        qs = Setor.objects.select_related(
            "unidade",
            "unidade__secretaria",
            "unidade__secretaria__municipio",
        ).filter(unidade_id__in=unidades_scope.values_list("id", flat=True))

        if unidade_id.isdigit():
            qs = qs.filter(unidade_id=int(unidade_id))

        return qs.order_by("nome")

    def apply_search(self, qs, q: str):
        return qs.filter(
            Q(nome__icontains=q)
            | Q(unidade__nome__icontains=q)
            | Q(unidade__secretaria__nome__icontains=q)
            | Q(unidade__secretaria__municipio__nome__icontains=q)
        )

    def get_extra_filters_html(self, request: HttpRequest, **kwargs) -> str:
        unidades_scope = scope_filter_unidades(
            request.user,
            Unidade.objects.select_related("secretaria", "secretaria__municipio").all()
        ).order_by("nome")
        unidade_id = (request.GET.get("unidade") or "").strip()
        return _unidade_select_html(unidades_scope, unidade_id)

    def get_actions(self, request, **kwargs):
        actions = super().get_actions(request, **kwargs)
        if is_admin(request.user):
            actions.insert(0, {"label": "Novo setor", "url": reverse("org:setor_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})
        # export
        actions.append({"label": "CSV", "url": request.path + "?export=csv", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"})
        actions.append({"label": "PDF", "url": request.path + "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"})
        return actions

    def get_headers(self, request):
        return [
            {"label": "Nome"},
            {"label": "Unidade"},
            {"label": "Secretaria"},
            {"label": "Município"},
            {"label": "Ativo", "width": "90px"},
        ]

    def get_rows(self, request, page_obj):
        rows = []
        can_edit = bool(is_admin(request.user))
        for s in page_obj.object_list:
            muni = s.unidade.secretaria.municipio if s.unidade and s.unidade.secretaria else None
            ativo_html = (
                f'<span class="status {"success" if s.ativo else "danger"}">'
                f'{"Sim" if s.ativo else "Não"}'
                f"</span>"
            )
            rows.append({
                "cells": [
                    {"text": s.nome, "url": reverse("org:setor_detail", args=[s.pk])},
                    {"text": s.unidade.nome if s.unidade else "—"},
                    {"text": s.unidade.secretaria.nome if (s.unidade and s.unidade.secretaria) else "—"},
                    {"text": f"{muni.nome}/{muni.uf}" if muni else "—"},
                    {"html": ativo_html, "safe": True},
                ],
                "can_edit": can_edit,
                "edit_url": reverse("org:setor_update", args=[s.pk]) if can_edit else "",
            })
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
            cols = [
                ("Nome", lambda o: o.nome),
                ("Unidade", lambda o: o.unidade.nome if o.unidade else ""),
                ("Secretaria", lambda o: o.unidade.secretaria.nome if (o.unidade and o.unidade.secretaria) else ""),
                ("Município", lambda o: f"{o.unidade.secretaria.municipio.nome}/{o.unidade.secretaria.municipio.uf}" if (o.unidade and o.unidade.secretaria and o.unidade.secretaria.municipio) else ""),
                ("Ativo", lambda o: "Sim" if o.ativo else "Não"),
            ]
            if export == "csv":
                return export_csv("setores.csv", items, cols)
            return export_pdf_table("Setores", items, cols)
        return super().get(request, *args, **kwargs)


class SetorCreateView(BaseCreateViewGepub):
    title = "Novo setor"
    subtitle = "Cadastre um setor vinculado a uma unidade"
    back_url_name = "org:setor_list"
    form_class = SetorForm
    submit_label = "Salvar setor"

    def dispatch(self, request, *args, **kwargs):
        if not is_admin(request.user):
            return HttpResponseForbidden("403 — Apenas administrador pode criar setor.")
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self, request, obj=None) -> str:
        return reverse("org:setor_detail", args=[obj.pk])


class SetorUpdateView(BaseUpdateViewGepub):
    title = "Editar setor"
    subtitle = "Atualize os dados do setor"
    back_url_name = "org:setor_list"
    form_class = SetorForm
    model = Setor
    submit_label = "Atualizar setor"

    def dispatch(self, request, *args, **kwargs):
        if not is_admin(request.user):
            return HttpResponseForbidden("403 — Apenas administrador pode editar setor.")
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self, request, obj=None) -> str:
        return reverse("org:setor_detail", args=[obj.pk])


class SetorDetailView(BaseDetailViewGepub):
    title = "Setor"
    subtitle = "Detalhes"
    back_url_name = "org:setor_list"
    model = Setor
    template_name = "org/setor_detail.html"

    def get(self, request, pk: int, *args, **kwargs):
        setor = get_object_or_404(Setor.objects.select_related("unidade__secretaria__municipio"), pk=pk)
        muni = setor.unidade.secretaria.municipio if setor.unidade and setor.unidade.secretaria else None

        actions = [{"label": "Voltar", "url": reverse("org:setor_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
        if is_admin(request.user):
            actions.append({"label": "Editar", "url": reverse("org:setor_update", args=[setor.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})

        fields = [
            {"label": "Nome", "value": setor.nome},
            {"label": "Unidade", "value": setor.unidade.nome if setor.unidade else "—"},
            {"label": "Secretaria", "value": setor.unidade.secretaria.nome if (setor.unidade and setor.unidade.secretaria) else "—"},
            {"label": "Município", "value": f"{muni.nome}/{muni.uf}" if muni else "—"},
            {"label": "Ativo", "value": "Sim" if setor.ativo else "Não"},
        ]

        return render(request, self.template_name, {
            "title": setor.nome,
            "subtitle": "Detalhes",
            "actions": actions,
            "obj": setor,
            "fields": fields,
            "pills": [],
        })


def setor_autocomplete(request: HttpRequest):
    q = (request.GET.get("q") or "").strip()
    unidades_scope = scope_filter_unidades(request.user, Unidade.objects.all())
    qs = Setor.objects.filter(unidade_id__in=unidades_scope.values_list("id", flat=True))
    if q:
        qs = qs.filter(Q(nome__icontains=q))
    items = list(qs.order_by("nome")[:20].values("id", "nome"))
    return JsonResponse({"results": [{"id": it["id"], "text": it["nome"]} for it in items]})
