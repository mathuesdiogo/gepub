from __future__ import annotations

import csv
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView
from weasyprint import HTML

from apps.core.models import DocumentoEmitido
from apps.core.exports import _try_make_qr_data_uri
from apps.core.rbac import get_profile, is_admin
from apps.educacao.models import Aluno, Matricula
from apps.org.models import Municipio, Unidade

from .forms import AlunoNecessidadeForm, ApoioMatriculaForm, TipoNecessidadeForm
from .models import AlunoNecessidade, ApoioMatricula, TipoNecessidade


# =========================================================
# BaseViews (modo seguro)
# - Preferimos usar as BaseViews do CORE, se existirem.
# - Caso não existam (ou o caminho mude), fazemos fallback
#   para wrappers mínimas (sem quebrar o projeto).
# =========================================================

BaseList = None
BaseCreate = None
BaseUpdate = None
BaseDetail = None
BaseDelete = None

for _path in (
    "apps.core.views",
    "apps.core.views.base",
    "apps.core.views.generics",
):
    try:
        mod = __import__(_path, fromlist=["BaseList", "BaseCreate", "BaseUpdate", "BaseDetail", "BaseDelete"])
        BaseList = getattr(mod, "BaseList", None) or getattr(mod, "BaseListView", None)
        BaseCreate = getattr(mod, "BaseCreate", None) or getattr(mod, "BaseCreateView", None)
        BaseUpdate = getattr(mod, "BaseUpdate", None) or getattr(mod, "BaseUpdateView", None)
        BaseDetail = getattr(mod, "BaseDetail", None) or getattr(mod, "BaseDetailView", None)
        BaseDelete = getattr(mod, "BaseDelete", None) or getattr(mod, "BaseDeleteView", None)
        if BaseList and BaseCreate and BaseUpdate and BaseDetail:
            break
    except Exception:
        continue


class _FallbackList(LoginRequiredMixin, ListView):
    """Fallback minimalista para manter padrão do projeto (actions/filters/table_shell)."""
    search_param = "q"
    paginate_by = 10

    def get_search_query(self) -> str:
        return (self.request.GET.get(self.search_param) or "").strip()

    def apply_search(self, qs, q: str):
        return qs

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.get_search_query()
        if q:
            qs = self.apply_search(qs, q)
        return qs

    def get_table_context(self) -> dict[str, Any]:
        return {"headers": [], "rows": []}

    def get_actions(self) -> list[dict[str, Any]]:
        return [{"label": "Voltar", "url": reverse("nee:index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = self.get_search_query()
        table = self.get_table_context()
        ctx.update({
            "q": q,
            "actions": self.get_actions(),
            "headers": table.get("headers", []),
            "rows": table.get("rows", []),
            "action_url": self.request.path,
            "clear_url": self.request.path,
            "has_filters": bool(q),
            "extra_filters": "",
        })
        return ctx


class _FallbackForm(LoginRequiredMixin):
    """Mixin para Create/Update fallback."""

    def get_actions(self) -> list[dict[str, Any]]:
        return [{"label": "Voltar", "url": reverse("nee:index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["actions"] = self.get_actions()
        return ctx


class _FallbackCreate(_FallbackForm, CreateView):
    pass


class _FallbackUpdate(_FallbackForm, UpdateView):
    pass


class _FallbackDetail(LoginRequiredMixin, DetailView):
    def get_actions(self) -> list[dict[str, Any]]:
        return [{"label": "Voltar", "url": reverse("nee:index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["actions"] = self.get_actions()
        return ctx


class _FallbackDelete(LoginRequiredMixin, DeleteView):
    pass


# Se o core tiver BaseViews, usa elas; se não, usa fallback.
BaseListView = BaseList or _FallbackList
BaseCreateView = BaseCreate or _FallbackCreate
BaseUpdateView = BaseUpdate or _FallbackUpdate
BaseDetailView = BaseDetail or _FallbackDetail
BaseDeleteView = BaseDelete or _FallbackDelete


@login_required
def index(request: HttpRequest) -> HttpResponse:
    actions = [
        {"label": "Tipos", "url": reverse("nee:tipo_list"), "icon": "fa-solid fa-list", "variant": "btn--ghost"},
        {"label": "Relatórios", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-chart-column", "variant": "btn-primary"},
    ]
    return render(request, "nee/index.html", {"actions": actions})


# =========================================================
# TIPOS DE NECESSIDADE (CRUD) — padrão BaseList/BaseCreate/...
# =========================================================

class TipoListView(BaseListView):
    model = TipoNecessidade
    template_name = "nee/tipo_list.html"
    paginate_by = 10
    search_param = "q"

    def apply_search(self, qs, q: str):
        return qs.filter(Q(nome__icontains=q))

    def get_actions(self):
        return [
            {"label": "Voltar", "url": reverse("nee:index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Novo tipo", "url": reverse("nee:tipo_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"},
        ]

    def get_table_context(self):
        headers = [{"label": "Nome"}, {"label": "Ativo", "width": "110px"}]
        rows = []
        for t in self.object_list:
            rows.append({
                "cells": [
                    {"text": t.nome, "url": reverse("nee:tipo_detail", args=[t.pk])},
                    {"text": "Sim" if t.ativo else "Não", "url": ""},
                ],
            })
        return {"headers": headers, "rows": rows}


class TipoDetailView(BaseDetailView):
    model = TipoNecessidade
    template_name = "nee/tipo_detail.html"
    context_object_name = "tipo"

    def get_actions(self):
        tipo = self.get_object()
        return [
            {"label": "Voltar", "url": reverse("nee:tipo_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Editar", "url": reverse("nee:tipo_update", args=[tipo.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"},
        ]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tipo: TipoNecessidade = ctx["tipo"]
        ctx.update({
            "page_title": tipo.nome,
            "page_subtitle": "Detalhes do tipo de necessidade",
            "fields": [{"label": "Nome", "value": tipo.nome}],
            "pills": [{"label": "Status", "value": "Ativo" if tipo.ativo else "Inativo", "variant": "success" if tipo.ativo else "danger"}],
        })
        return ctx


class TipoCreateView(BaseCreateView):
    model = TipoNecessidade
    form_class = TipoNecessidadeForm
    template_name = "nee/tipo_form.html"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Tipo de necessidade criado com sucesso.")
        return resp

    def form_invalid(self, form):
        messages.error(self.request, "Corrija os erros do formulário.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("nee:tipo_detail", args=[self.object.pk])

    def get_actions(self):
        return [{"label": "Voltar", "url": reverse("nee:tipo_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]


class TipoUpdateView(BaseUpdateView):
    model = TipoNecessidade
    form_class = TipoNecessidadeForm
    template_name = "nee/tipo_form.html"
    context_object_name = "tipo"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Tipo de necessidade atualizado com sucesso.")
        return resp

    def form_invalid(self, form):
        messages.error(self.request, "Corrija os erros do formulário.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("nee:tipo_detail", args=[self.object.pk])

    def get_actions(self):
        tipo = self.get_object()
        return [{"label": "Voltar", "url": reverse("nee:tipo_detail", args=[tipo.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]


# =========================================================
# NECESSIDADES DO ALUNO (CRUD por aluno)
# =========================================================

class AlunoNecessidadeListView(BaseListView):
    model = AlunoNecessidade
    template_name = "nee/aluno_necessidade_list.html"
    paginate_by = 10
    search_param = "q"

    def dispatch(self, request, *args, **kwargs):
        self.aluno = get_object_or_404(Aluno, pk=kwargs["aluno_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("tipo", "aluno")
            .filter(aluno=self.aluno)
            .order_by("-id")
        )
        q = (self.request.GET.get(self.search_param) or "").strip()
        if q:
            qs = qs.filter(Q(tipo__nome__icontains=q) | Q(cid__icontains=q))
        return qs

    def get_actions(self):
        return [
            {"label": "Voltar", "url": reverse("educacao:aluno_detail", args=[self.aluno.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Nova necessidade", "url": reverse("nee:aluno_necessidade_create", args=[self.aluno.pk]), "icon": "fa-solid fa-plus", "variant": "btn-primary"},
        ]

    def get_table_context(self):
        headers = [
            {"label": "Tipo"},
            {"label": "CID", "width": "140px"},
            {"label": "Ativo", "width": "110px"},
        ]
        rows = []
        for n in self.object_list:
            rows.append({
                "cells": [
                    {"text": n.tipo.nome, "url": reverse("nee:aluno_necessidade_detail", args=[self.aluno.pk, n.pk])},
                    {"text": n.cid or "—", "url": ""},
                    {"text": "Sim" if n.ativo else "Não", "url": ""},
                ],
            })
        return {"headers": headers, "rows": rows}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["aluno"] = self.aluno
        ctx["page_title"] = f"NEE • {self.aluno.nome}"
        ctx["page_subtitle"] = "Necessidades educacionais especiais do aluno"
        return ctx


class AlunoNecessidadeDetailView(BaseDetailView):
    model = AlunoNecessidade
    template_name = "nee/aluno_necessidade_detail.html"
    context_object_name = "obj"

    def dispatch(self, request, *args, **kwargs):
        self.aluno = get_object_or_404(Aluno, pk=kwargs["aluno_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().select_related("tipo", "aluno").filter(aluno=self.aluno)

    def get_actions(self):
        obj = self.get_object()
        return [
            {"label": "Voltar", "url": reverse("nee:aluno_necessidade_list", args=[self.aluno.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Editar", "url": reverse("nee:aluno_necessidade_update", args=[self.aluno.pk, obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"},
        ]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj: AlunoNecessidade = ctx["obj"]
        ctx["aluno"] = self.aluno
        ctx["page_title"] = "Detalhes da necessidade"
        ctx["page_subtitle"] = self.aluno.nome
        ctx["fields"] = [
            {"label": "Tipo", "value": obj.tipo.nome},
            {"label": "CID", "value": obj.cid or "—"},
            {"label": "Observação", "value": obj.observacao or "—"},
        ]
        ctx["pills"] = [{"label": "Status", "value": "Ativo" if obj.ativo else "Inativo", "variant": "success" if obj.ativo else "danger"}]
        return ctx


class AlunoNecessidadeCreateView(BaseCreateView):
    model = AlunoNecessidade
    form_class = AlunoNecessidadeForm
    template_name = "nee/aluno_necessidade_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.aluno = get_object_or_404(Aluno, pk=kwargs["aluno_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["aluno"] = self.aluno
        return kwargs

    def form_valid(self, form):
        form.instance.aluno = self.aluno
        resp = super().form_valid(form)
        messages.success(self.request, "Necessidade adicionada com sucesso.")
        return resp

    def form_invalid(self, form):
        messages.error(self.request, "Corrija os erros do formulário.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("nee:aluno_necessidade_detail", args=[self.aluno.pk, self.object.pk])

    def get_actions(self):
        return [{"label": "Voltar", "url": reverse("nee:aluno_necessidade_list", args=[self.aluno.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["aluno"] = self.aluno
        ctx["mode"] = "create"
        return ctx


class AlunoNecessidadeUpdateView(BaseUpdateView):
    model = AlunoNecessidade
    form_class = AlunoNecessidadeForm
    template_name = "nee/aluno_necessidade_form.html"
    context_object_name = "obj"

    def dispatch(self, request, *args, **kwargs):
        self.aluno = get_object_or_404(Aluno, pk=kwargs["aluno_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().filter(aluno=self.aluno)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["aluno"] = self.aluno
        return kwargs

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Necessidade atualizada com sucesso.")
        return resp

    def form_invalid(self, form):
        messages.error(self.request, "Corrija os erros do formulário.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("nee:aluno_necessidade_detail", args=[self.aluno.pk, self.object.pk])

    def get_actions(self):
        obj = self.get_object()
        return [{"label": "Voltar", "url": reverse("nee:aluno_necessidade_detail", args=[self.aluno.pk, obj.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["aluno"] = self.aluno
        ctx["mode"] = "update"
        return ctx


# =========================================================
# APOIOS DA MATRÍCULA (CRUD) — opcional, focado em aluno
# =========================================================

class ApoioListView(BaseListView):
    model = ApoioMatricula
    template_name = "nee/apoio_list.html"
    paginate_by = 10

    def dispatch(self, request, *args, **kwargs):
        self.aluno = get_object_or_404(Aluno, pk=kwargs["aluno_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("matricula", "matricula__turma")
            .filter(matricula__aluno=self.aluno)
            .order_by("-id")
        )

    def get_actions(self):
        return [
            {"label": "Voltar", "url": reverse("educacao:aluno_detail", args=[self.aluno.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Novo apoio", "url": reverse("nee:apoio_create", args=[self.aluno.pk]), "icon": "fa-solid fa-plus", "variant": "btn-primary"},
        ]

    def get_table_context(self):
        headers = [{"label": "Matrícula"}, {"label": "Tipo"}, {"label": "CH/sem", "width": "110px"}, {"label": "Ativo", "width": "110px"}]
        rows = []
        for a in self.object_list:
            rows.append({
                "cells": [
                    {"text": str(a.matricula), "url": reverse("nee:apoio_detail", args=[self.aluno.pk, a.pk])},
                    {"text": a.get_tipo_display(), "url": ""},
                    {"text": str(a.carga_horaria_semanal) if a.carga_horaria_semanal is not None else "—", "url": ""},
                    {"text": "Sim" if a.ativo else "Não", "url": ""},
                ],
            })
        return {"headers": headers, "rows": rows}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["aluno"] = self.aluno
        ctx["page_title"] = f"Apoios • {self.aluno.nome}"
        ctx["page_subtitle"] = "Apoios vinculados às matrículas do aluno"
        return ctx


class ApoioDetailView(BaseDetailView):
    model = ApoioMatricula
    template_name = "nee/apoio_detail.html"
    context_object_name = "obj"

    def dispatch(self, request, *args, **kwargs):
        self.aluno = get_object_or_404(Aluno, pk=kwargs["aluno_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().select_related("matricula", "matricula__turma").filter(matricula__aluno=self.aluno)

    def get_actions(self):
        obj = self.get_object()
        return [
            {"label": "Voltar", "url": reverse("nee:apoio_list", args=[self.aluno.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
            {"label": "Editar", "url": reverse("nee:apoio_update", args=[self.aluno.pk, obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"},
        ]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj: ApoioMatricula = ctx["obj"]
        ctx["aluno"] = self.aluno
        ctx["page_title"] = "Detalhes do apoio"
        ctx["page_subtitle"] = self.aluno.nome
        ctx["fields"] = [
            {"label": "Matrícula", "value": str(obj.matricula)},
            {"label": "Tipo", "value": obj.get_tipo_display()},
            {"label": "Descrição", "value": obj.descricao or "—"},
            {"label": "Carga horária semanal", "value": str(obj.carga_horaria_semanal) if obj.carga_horaria_semanal is not None else "—"},
        ]
        ctx["pills"] = [{"label": "Status", "value": "Ativo" if obj.ativo else "Inativo", "variant": "success" if obj.ativo else "danger"}]
        return ctx


class ApoioCreateView(BaseCreateView):
    model = ApoioMatricula
    form_class = ApoioMatriculaForm
    template_name = "nee/apoio_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.aluno = get_object_or_404(Aluno, pk=kwargs["aluno_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["aluno"] = self.aluno
        return kwargs

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Apoio criado com sucesso.")
        return resp

    def form_invalid(self, form):
        messages.error(self.request, "Corrija os erros do formulário.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("nee:apoio_detail", args=[self.aluno.pk, self.object.pk])

    def get_actions(self):
        return [{"label": "Voltar", "url": reverse("nee:apoio_list", args=[self.aluno.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["aluno"] = self.aluno
        ctx["mode"] = "create"
        return ctx


class ApoioUpdateView(BaseUpdateView):
    model = ApoioMatricula
    form_class = ApoioMatriculaForm
    template_name = "nee/apoio_form.html"
    context_object_name = "obj"

    def dispatch(self, request, *args, **kwargs):
        self.aluno = get_object_or_404(Aluno, pk=kwargs["aluno_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().filter(matricula__aluno=self.aluno)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["aluno"] = self.aluno
        return kwargs

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Apoio atualizado com sucesso.")
        return resp

    def form_invalid(self, form):
        messages.error(self.request, "Corrija os erros do formulário.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("nee:apoio_detail", args=[self.aluno.pk, self.object.pk])

    def get_actions(self):
        obj = self.get_object()
        return [{"label": "Voltar", "url": reverse("nee:apoio_detail", args=[self.aluno.pk, obj.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["aluno"] = self.aluno
        ctx["mode"] = "update"
        return ctx


# =========================================================
# RELATÓRIOS (mantém função-based por ser geração/exports)
# =========================================================

@login_required
def relatorios_index(request: HttpRequest) -> HttpResponse:
    actions = [{"label": "Voltar", "url": reverse("nee:index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    return render(request, "nee/relatorios/index.html", {"actions": actions})


def _aplicar_rbac_relatorios(request: HttpRequest, municipio_id: str, unidade_id: str):
    """Força filtros de município/unidade baseado no Profile. Admin vê tudo."""
    if is_admin(request.user):
        return municipio_id, unidade_id

    p = get_profile(request.user)
    if getattr(p, "municipio_id", None):
        municipio_id = str(p.municipio_id)
    if getattr(p, "unidade_id", None):
        unidade_id = str(p.unidade_id)
    return municipio_id, unidade_id


def _build_extra_filters_html(municipio_id: str, unidade_id: str):
    parts = []
    if municipio_id:
        m = Municipio.objects.filter(pk=municipio_id).first()
        if m:
            parts.append(f"<span class='pill'>Município: {escape(m.nome)}</span>")
    if unidade_id:
        u = Unidade.objects.filter(pk=unidade_id).first()
        if u:
            parts.append(f"<span class='pill'>Unidade: {escape(u.nome)}</span>")
    return mark_safe(" ".join(parts))


def _matriculas_base():
    return (
        Matricula.objects
        .select_related("aluno", "turma", "turma__unidade", "turma__unidade__secretaria", "turma__unidade__secretaria__municipio")
        .filter(ativo=True)
    )


def _aplicar_filtros_matriculas(qs, municipio_id: str, unidade_id: str):
    if municipio_id:
        qs = qs.filter(turma__unidade__secretaria__municipio_id=municipio_id)
    if unidade_id:
        qs = qs.filter(turma__unidade_id=unidade_id)
    return qs


def _csv_response(filename: str, rows: list[list[str]]) -> HttpResponse:
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    resp.write("\ufeff")  # BOM
    w = csv.writer(resp, delimiter=";")
    for r in rows:
        w.writerow(r)
    return resp


def _pdf_response(request: HttpRequest, template_name: str, context: dict[str, Any], doc_tipo: str, filename: str) -> HttpResponse:
    html = render_to_string(template_name, context)
    qr_data = _try_make_qr_data_uri(request, context.get("doc_url", ""))
    pdf = HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()

    doc = DocumentoEmitido.objects.create(
        tipo=doc_tipo,
        codigo=context.get("codigo", ""),
        usuario=request.user,
        gerado_em=timezone.now(),
    )

    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="{filename}"'
    return resp


@login_required
def relatorio_por_tipo(request: HttpRequest) -> HttpResponse:
    municipio_id = request.GET.get("municipio") or ""
    unidade_id = request.GET.get("unidade") or ""
    municipio_id, unidade_id = _aplicar_rbac_relatorios(request, municipio_id, unidade_id)

    qs = _matriculas_base()
    qs = _aplicar_filtros_matriculas(qs, municipio_id, unidade_id)

    # agrega necessidades por tipo
    data = (
        AlunoNecessidade.objects
        .filter(aluno__matriculas__in=qs)
        .values("tipo__nome")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    actions = [{"label": "Voltar", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    extra_filters = _build_extra_filters_html(municipio_id, unidade_id)

    if request.GET.get("export") == "csv":
        rows = [["Tipo", "Total"]] + [[d["tipo__nome"], str(d["total"])] for d in data]
        return _csv_response("nee_por_tipo.csv", rows)

    return render(request, "nee/relatorios/por_tipo.html", {
        "actions": actions,
        "data": data,
        "extra_filters": extra_filters,
    })


@login_required
def relatorio_por_municipio(request: HttpRequest) -> HttpResponse:
    qs = _matriculas_base()

    data = (
        AlunoNecessidade.objects
        .filter(aluno__matriculas__in=qs)
        .values("aluno__matriculas__turma__unidade__secretaria__municipio__nome")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    actions = [{"label": "Voltar", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]

    if request.GET.get("export") == "csv":
        rows = [["Município", "Total"]] + [[d["aluno__matriculas__turma__unidade__secretaria__municipio__nome"], str(d["total"])] for d in data]
        return _csv_response("nee_por_municipio.csv", rows)

    return render(request, "nee/relatorios/por_municipio.html", {"actions": actions, "data": data})


@login_required
def relatorio_por_unidade(request: HttpRequest) -> HttpResponse:
    municipio_id = request.GET.get("municipio") or ""
    unidade_id = request.GET.get("unidade") or ""
    municipio_id, unidade_id = _aplicar_rbac_relatorios(request, municipio_id, unidade_id)

    qs = _matriculas_base()
    qs = _aplicar_filtros_matriculas(qs, municipio_id, unidade_id)

    data = (
        AlunoNecessidade.objects
        .filter(aluno__matriculas__in=qs)
        .values("aluno__matriculas__turma__unidade__nome")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    actions = [{"label": "Voltar", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    extra_filters = _build_extra_filters_html(municipio_id, unidade_id)

    if request.GET.get("export") == "csv":
        rows = [["Unidade", "Total"]] + [[d["aluno__matriculas__turma__unidade__nome"], str(d["total"])] for d in data]
        return _csv_response("nee_por_unidade.csv", rows)

    return render(request, "nee/relatorios/por_unidade.html", {
        "actions": actions,
        "data": data,
        "extra_filters": extra_filters,
    })
