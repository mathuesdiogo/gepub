from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import can, is_admin, scope_filter_unidades
from apps.org.models import Unidade

from .forms import CoordenacaoEnsinoForm, CursoDisciplinaForm, CursoForm
from .models import CoordenacaoEnsino, Curso, CursoDisciplina


@login_required
@require_perm("educacao.view")
def curso_list(request):
    q = (request.GET.get("q") or "").strip()
    can_manage = can(request.user, "educacao.manage")
    qs = Curso.objects.annotate(
        total_disciplinas=Count("disciplinas", distinct=True),
        total_alunos=Count("matriculas_alunos", distinct=True),
    )
    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(codigo__icontains=q)
            | Q(eixo_tecnologico__icontains=q)
        )

    page_obj = Paginator(qs.order_by("nome"), 20).get_page(request.GET.get("page"))

    rows = []
    for curso in page_obj:
        rows.append(
            {
                "cells": [
                    {"text": curso.nome},
                    {"text": curso.codigo or "—"},
                    {"text": curso.get_modalidade_oferta_display()},
                    {"text": curso.eixo_tecnologico or "—"},
                    {"text": str(curso.carga_horaria or 0)},
                    {"text": str(getattr(curso, "total_disciplinas", 0))},
                    {"text": str(getattr(curso, "total_alunos", 0))},
                    {"text": "Sim" if curso.ativo else "Não"},
                ],
                "can_edit": can_manage,
                "edit_url": reverse("educacao:curso_update", args=[curso.pk]) if can_manage else "",
            }
        )

    actions = []
    if can_manage:
        actions.append(
            {
                "label": "Novo Curso",
                "url": reverse("educacao:curso_create"),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            }
        )
    actions.append(
        {
            "label": "Voltar",
            "url": reverse("educacao:index"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }
    )

    return render(
        request,
        "educacao/curso_list.html",
        {
            "q": q,
            "page_obj": page_obj,
            "actions": actions,
            "headers": [
                {"label": "Nome"},
                {"label": "Código", "width": "130px"},
                {"label": "Modalidade"},
                {"label": "Eixo"},
                {"label": "Carga Horária", "width": "130px"},
                {"label": "Grade", "width": "100px"},
                {"label": "Alunos", "width": "100px"},
                {"label": "Ativo", "width": "100px"},
            ],
            "rows": rows,
            "action_url": reverse("educacao:curso_list"),
            "clear_url": reverse("educacao:curso_list"),
            "has_filters": False,
        },
    )


@login_required
@require_perm("educacao.manage")
def curso_create(request):
    form = CursoForm(request.POST or None)
    grade_form = CursoDisciplinaForm(request.POST or None, prefix="grade")
    if request.method == "POST":
        wants_first_disciplina = bool((request.POST.get("grade-nome") or "").strip())
        grade_ok = (not wants_first_disciplina) or grade_form.is_valid()

        if form.is_valid() and grade_ok:
            curso = form.save()
            if wants_first_disciplina:
                disciplina = grade_form.save(commit=False)
                disciplina.curso = curso
                disciplina.save()
            messages.success(request, "Curso cadastrado com sucesso.")
            return redirect("educacao:curso_update", pk=curso.pk)
        if wants_first_disciplina and not grade_ok:
            messages.error(request, "Corrija os erros da disciplina inicial da grade.")
        elif not form.is_valid():
            messages.error(request, "Corrija os erros do curso.")

    return render(
        request,
        "educacao/curso_form.html",
        {
            "form": form,
            "grade_form": grade_form,
            "mode": "create",
            "cancel_url": reverse("educacao:curso_list"),
            "submit_label": "Salvar curso",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:curso_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("educacao.manage")
def curso_update(request, pk: int):
    curso = get_object_or_404(Curso, pk=pk)
    form = CursoForm(request.POST or None, instance=curso)
    grade_form = CursoDisciplinaForm(request.POST or None, prefix="grade")

    if request.method == "POST":
        action = (request.POST.get("_action") or "save_curso").strip()
        if action == "add_disciplina":
            if grade_form.is_valid():
                disciplina = grade_form.save(commit=False)
                disciplina.curso = curso
                disciplina.save()
                messages.success(request, "Disciplina adicionada à grade curricular.")
                return redirect("educacao:curso_update", pk=curso.pk)
            messages.error(request, "Corrija os erros da disciplina.")
        elif action == "remove_disciplina":
            disciplina_id = (request.POST.get("disciplina_id") or "").strip()
            if disciplina_id.isdigit():
                disciplina = get_object_or_404(CursoDisciplina, pk=int(disciplina_id), curso=curso)
                disciplina.delete()
                messages.success(request, "Disciplina removida da grade.")
            return redirect("educacao:curso_update", pk=curso.pk)
        else:
            if form.is_valid():
                form.save()
                messages.success(request, "Curso atualizado com sucesso.")
                return redirect("educacao:curso_update", pk=curso.pk)
            messages.error(request, "Corrija os erros do curso.")

    disciplinas = curso.disciplinas.order_by("ordem", "nome")

    return render(
        request,
        "educacao/curso_form.html",
        {
            "form": form,
            "grade_form": grade_form,
            "disciplinas": disciplinas,
            "mode": "update",
            "curso": curso,
            "cancel_url": reverse("educacao:curso_list"),
            "submit_label": "Atualizar curso",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:curso_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("educacao.view")
def coordenacao_list(request):
    q = (request.GET.get("q") or "").strip()
    modalidade = (request.GET.get("modalidade") or "").strip()
    can_manage = can(request.user, "educacao.manage")

    qs = CoordenacaoEnsino.objects.select_related(
        "unidade",
        "unidade__secretaria",
        "unidade__secretaria__municipio",
        "coordenador",
    )
    allowed_unidades = scope_filter_unidades(request.user, Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO))
    qs = qs.filter(unidade__in=allowed_unidades)

    if q:
        qs = qs.filter(
            Q(coordenador__username__icontains=q)
            | Q(coordenador__first_name__icontains=q)
            | Q(coordenador__last_name__icontains=q)
            | Q(unidade__nome__icontains=q)
        )
    if modalidade:
        qs = qs.filter(modalidade=modalidade)

    page_obj = Paginator(qs.order_by("unidade__nome", "modalidade"), 20).get_page(request.GET.get("page"))
    rows = []
    for item in page_obj:
        nome = item.coordenador.get_full_name().strip() or item.coordenador.username
        rows.append(
            {
                "cells": [
                    {"text": nome},
                    {"text": item.get_modalidade_display()},
                    {"text": item.get_etapa_display() if item.etapa else "—"},
                    {"text": item.unidade.nome},
                    {"text": item.inicio.strftime("%d/%m/%Y") if item.inicio else "—"},
                    {"text": item.fim.strftime("%d/%m/%Y") if item.fim else "—"},
                    {"text": "Ativo" if item.ativo else "Inativo"},
                ],
                "can_edit": can_manage,
                "edit_url": reverse("educacao:coordenacao_update", args=[item.pk]) if can_manage else "",
            }
        )

    modalidades_options = "".join(
        [
            f'<option value="{value}" {"selected" if modalidade == value else ""}>{label}</option>'
            for value, label in CoordenacaoEnsino._meta.get_field("modalidade").choices
        ]
    )

    actions = [
        {
            "label": "Voltar",
            "url": reverse("educacao:index"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        },
    ]
    if can_manage:
        actions.insert(
            0,
            {
                "label": "Nova Coordenação",
                "url": reverse("educacao:coordenacao_create"),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            },
        )

    extra_filters = f"""
      <div class="filter-bar__field">
        <label class="small">Modalidade</label>
        <select name="modalidade">
          <option value="">Todas</option>
          {modalidades_options}
        </select>
      </div>
    """

    return render(
        request,
        "educacao/coordenacao_list.html",
        {
            "q": q,
            "page_obj": page_obj,
            "actions": actions,
            "headers": [
                {"label": "Coordenador"},
                {"label": "Modalidade"},
                {"label": "Etapa"},
                {"label": "Unidade"},
                {"label": "Início", "width": "120px"},
                {"label": "Fim", "width": "120px"},
                {"label": "Status", "width": "120px"},
            ],
            "rows": rows,
            "action_url": reverse("educacao:coordenacao_list"),
            "clear_url": reverse("educacao:coordenacao_list"),
            "extra_filters": extra_filters,
            "has_filters": bool(modalidade),
        },
    )


@login_required
@require_perm("educacao.manage")
def coordenacao_create(request):
    form = CoordenacaoEnsinoForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Coordenação cadastrada com sucesso.")
        return redirect("educacao:coordenacao_list")

    return render(
        request,
        "educacao/coordenacao_form.html",
        {
            "form": form,
            "mode": "create",
            "cancel_url": reverse("educacao:coordenacao_list"),
            "submit_label": "Salvar coordenação",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:coordenacao_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("educacao.manage")
def coordenacao_update(request, pk: int):
    obj = get_object_or_404(CoordenacaoEnsino, pk=pk)
    if not is_admin(request.user):
        allowed = scope_filter_unidades(
            request.user,
            Unidade.objects.filter(pk=obj.unidade_id),
        ).exists()
        if not allowed:
            messages.error(request, "Você não tem acesso a esta coordenação.")
            return redirect("educacao:coordenacao_list")

    form = CoordenacaoEnsinoForm(request.POST or None, instance=obj, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Coordenação atualizada com sucesso.")
        return redirect("educacao:coordenacao_list")

    return render(
        request,
        "educacao/coordenacao_form.html",
        {
            "form": form,
            "mode": "update",
            "coordenacao": obj,
            "cancel_url": reverse("educacao:coordenacao_list"),
            "submit_label": "Atualizar coordenação",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:coordenacao_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )
