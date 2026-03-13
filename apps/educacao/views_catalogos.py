from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils import timezone

from apps.core.decorators import require_perm
from apps.core.exports import export_csv, export_pdf_table
from apps.core.rbac import can, is_admin, scope_filter_unidades
from apps.org.models import Secretaria, Unidade

from .forms import (
    CoordenacaoEnsinoForm,
    CursoDisciplinaForm,
    CursoForm,
    MatrizComponenteForm,
    MatrizEquivalenciaGrupoForm,
    MatrizEquivalenciaItemForm,
    MatrizComponenteRelacaoForm,
    MatrizCurricularForm,
)
from .models import (
    CoordenacaoEnsino,
    Curso,
    CursoDisciplina,
    MatrizComponente,
    MatrizComponenteEquivalenciaGrupo,
    MatrizComponenteEquivalenciaItem,
    MatrizComponenteRelacao,
    MatrizCurricular,
)
from .services_turma_setup import (
    clonar_matriz_para_ano,
    preencher_componentes_base_matriz,
)
from .services_matriz_modelos import (
    MODELO_REDE_CHOICES,
    aplicar_modelo_importado_para_unidades,
    aplicar_modelo_oficial_para_unidades,
    importar_modelo_csv,
)


def _resolver_matriz_com_escopo(request, pk: int) -> MatrizCurricular | None:
    matriz = get_object_or_404(
        MatrizCurricular.objects.select_related("unidade", "unidade__secretaria"),
        pk=pk,
    )
    if not is_admin(request.user):
        allowed = scope_filter_unidades(request.user, Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO))
        if not allowed.filter(pk=matriz.unidade_id).exists():
            return None
    return matriz


class MatrizModelosOficiaisForm(forms.Form):
    rede_modelo = forms.ChoiceField(label="Modelo da rede", choices=MODELO_REDE_CHOICES)
    ano_referencia = forms.IntegerField(label="Ano de referência", min_value=2000, max_value=2200)
    secretaria = forms.ModelChoiceField(
        label="Secretaria (opcional)",
        queryset=Secretaria.objects.none(),
        required=False,
        empty_label="Todas as secretarias no seu escopo",
    )
    unidades = forms.ModelMultipleChoiceField(
        label="Unidades de educação (opcional)",
        queryset=Unidade.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 8}),
    )
    sobrescrever_existentes = forms.BooleanField(
        label="Sobrescrever matrizes/componentes existentes no mesmo ano",
        required=False,
    )

    def __init__(self, *args, secretarias_qs, unidades_qs, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["secretaria"].queryset = secretarias_qs.order_by("nome")
        self.fields["unidades"].queryset = unidades_qs.order_by("nome")

        secretaria_raw = ""
        if self.is_bound:
            secretaria_raw = (self.data.get(self.add_prefix("secretaria")) or "").strip()
        else:
            secretaria_raw = str(self.initial.get("secretaria") or "").strip()
        if secretaria_raw.isdigit():
            self.fields["unidades"].queryset = self.fields["unidades"].queryset.filter(secretaria_id=int(secretaria_raw))


class MatrizModeloImportCsvForm(forms.Form):
    arquivo_csv = forms.FileField(label="Arquivo CSV")
    ano_referencia = forms.IntegerField(label="Ano de referência", min_value=2000, max_value=2200)
    secretaria = forms.ModelChoiceField(
        label="Secretaria (opcional)",
        queryset=Secretaria.objects.none(),
        required=False,
        empty_label="Todas as secretarias no seu escopo",
    )
    unidades = forms.ModelMultipleChoiceField(
        label="Unidades de educação (opcional)",
        queryset=Unidade.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 8}),
    )
    sobrescrever_existentes = forms.BooleanField(
        label="Sobrescrever matrizes/componentes existentes no mesmo ano",
        required=False,
    )

    def __init__(self, *args, secretarias_qs, unidades_qs, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["secretaria"].queryset = secretarias_qs.order_by("nome")
        self.fields["unidades"].queryset = unidades_qs.order_by("nome")

        secretaria_raw = ""
        if self.is_bound:
            secretaria_raw = (self.data.get(self.add_prefix("secretaria")) or "").strip()
        else:
            secretaria_raw = str(self.initial.get("secretaria") or "").strip()
        if secretaria_raw.isdigit():
            self.fields["unidades"].queryset = self.fields["unidades"].queryset.filter(secretaria_id=int(secretaria_raw))


def _unidades_educacao_scope(request):
    return scope_filter_unidades(request.user, Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO)).select_related(
        "secretaria",
        "secretaria__municipio",
    )


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
                "label": "Nova Atividade Extra",
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
                {"label": "Componentes", "width": "110px"},
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
            messages.success(request, "Atividade extracurricular cadastrada com sucesso.")
            return redirect("educacao:curso_update", pk=curso.pk)
        if wants_first_disciplina and not grade_ok:
            messages.error(request, "Corrija os erros da disciplina inicial da grade.")
        elif not form.is_valid():
            messages.error(request, "Corrija os erros da atividade extracurricular.")

    return render(
        request,
        "educacao/curso_form.html",
        {
            "form": form,
            "grade_form": grade_form,
            "mode": "create",
            "cancel_url": reverse("educacao:curso_list"),
            "submit_label": "Salvar atividade extra",
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
                messages.success(request, "Atividade extracurricular atualizada com sucesso.")
                return redirect("educacao:curso_update", pk=curso.pk)
            messages.error(request, "Corrija os erros da atividade extracurricular.")

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
            "submit_label": "Atualizar atividade extra",
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
def matriz_list(request):
    q = (request.GET.get("q") or "").strip()
    etapa = (request.GET.get("etapa") or "").strip()
    can_manage = can(request.user, "educacao.manage")

    qs = MatrizCurricular.objects.select_related(
        "unidade",
        "unidade__secretaria",
        "unidade__secretaria__municipio",
    ).annotate(total_componentes=Count("componentes", distinct=True))
    qs = qs.filter(unidade__in=scope_filter_unidades(request.user, Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO)))

    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(unidade__nome__icontains=q)
            | Q(unidade__secretaria__nome__icontains=q)
        )
    if etapa:
        qs = qs.filter(etapa_base=etapa)

    page_obj = Paginator(qs.order_by("-ano_referencia", "etapa_base", "serie_ano", "nome"), 20).get_page(
        request.GET.get("page")
    )

    rows = []
    for item in page_obj:
        rows.append(
            {
                "cells": [
                    {"text": item.nome},
                    {"text": item.get_etapa_base_display()},
                    {"text": item.get_serie_ano_display()},
                    {"text": str(item.ano_referencia)},
                    {"text": item.unidade.nome},
                    {"text": str(getattr(item, "total_componentes", 0))},
                    {"text": "Sim" if item.ativo else "Não"},
                ],
                "can_edit": can_manage,
                "edit_url": reverse("educacao:matriz_update", args=[item.pk]) if can_manage else "",
            }
        )

    actions = [
        {
            "label": "Voltar",
            "url": reverse("educacao:index"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }
    ]
    if can_manage:
        actions.insert(
            0,
            {
                "label": "Modelos Oficiais",
                "url": reverse("educacao:matriz_modelos"),
                "icon": "fa-solid fa-layer-group",
                "variant": "btn--ghost",
            },
        )
        actions.insert(
            0,
            {
                "label": "Nova Matriz",
                "url": reverse("educacao:matriz_create"),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            },
        )

    etapa_options = format_html_join(
        "",
        '<option value="{}"{}>{}</option>',
        ((value, " selected" if etapa == value else "", label) for value, label in MatrizCurricular.EtapaBase.choices),
    )
    extra_filters = str(
        format_html(
            (
                '<div class="filter-bar__field"><label class="small">Etapa</label><select name="etapa">'
                '<option value="">Todas</option>{}</select></div>'
            ),
            etapa_options,
        )
    )

    return render(
        request,
        "educacao/matriz_list.html",
        {
            "q": q,
            "page_obj": page_obj,
            "actions": actions,
            "headers": [
                {"label": "Matriz"},
                {"label": "Etapa"},
                {"label": "Série/Ano", "width": "170px"},
                {"label": "Ano Ref.", "width": "120px"},
                {"label": "Unidade"},
                {"label": "Componentes", "width": "130px"},
                {"label": "Ativa", "width": "100px"},
            ],
            "rows": rows,
            "action_url": reverse("educacao:matriz_list"),
            "clear_url": reverse("educacao:matriz_list"),
            "extra_filters": extra_filters,
            "has_filters": bool(etapa),
        },
    )


@login_required
@require_perm("educacao.manage")
def matriz_modelos(request):
    unidades_scope = _unidades_educacao_scope(request).order_by("secretaria__nome", "nome")
    secretarias_ids = list(unidades_scope.values_list("secretaria_id", flat=True).distinct())
    secretarias_qs = Secretaria.objects.filter(id__in=secretarias_ids)

    initial = {"ano_referencia": timezone.localdate().year}
    oficiais_form = MatrizModelosOficiaisForm(
        request.POST or None,
        prefix="oficial",
        secretarias_qs=secretarias_qs,
        unidades_qs=unidades_scope,
        initial=initial,
    )
    import_form = MatrizModeloImportCsvForm(
        request.POST or None,
        request.FILES or None,
        prefix="import",
        secretarias_qs=secretarias_qs,
        unidades_qs=unidades_scope,
        initial=initial,
    )

    def resolver_unidades(cleaned_data: dict) -> list[Unidade]:
        unidades_selecionadas = list(cleaned_data.get("unidades") or [])
        if unidades_selecionadas:
            allowed_ids = set(unidades_scope.values_list("id", flat=True))
            return [u for u in unidades_selecionadas if u.id in allowed_ids]

        secretaria = cleaned_data.get("secretaria")
        qs = unidades_scope
        if secretaria:
            qs = qs.filter(secretaria=secretaria)
        return list(qs.order_by("nome"))

    if request.method == "POST":
        action = (request.POST.get("_action") or "").strip()

        if action == "aplicar_oficial":
            if oficiais_form.is_valid():
                unidades = resolver_unidades(oficiais_form.cleaned_data)
                if not unidades:
                    messages.error(request, "Selecione ao menos uma unidade para aplicar o modelo oficial.")
                else:
                    resumo = aplicar_modelo_oficial_para_unidades(
                        rede=oficiais_form.cleaned_data["rede_modelo"],
                        ano_referencia=oficiais_form.cleaned_data["ano_referencia"],
                        unidades=unidades,
                        sobrescrever_existentes=bool(oficiais_form.cleaned_data.get("sobrescrever_existentes")),
                    )
                    messages.success(
                        request,
                        (
                            f"Modelo oficial aplicado em {len(unidades)} unidade(s). "
                            f"Matrizes criadas: {resumo.matrizes_criadas}, "
                            f"atualizadas: {resumo.matrizes_atualizadas}, "
                            f"ignoradas: {resumo.matrizes_ignoradas}, "
                            f"componentes novos: {resumo.componentes_criados}, "
                            f"componentes atualizados: {resumo.componentes_atualizados}."
                        ),
                    )
                return redirect("educacao:matriz_modelos")
            messages.error(request, "Corrija os erros do formulário de modelos oficiais.")

        elif action == "importar_csv":
            if import_form.is_valid():
                unidades = resolver_unidades(import_form.cleaned_data)
                if not unidades:
                    messages.error(request, "Selecione ao menos uma unidade para aplicar o modelo importado.")
                    return redirect("educacao:matriz_modelos")

                arquivo = import_form.cleaned_data["arquivo_csv"]
                try:
                    modelo_importado = importar_modelo_csv(arquivo.read())
                except ValueError as exc:
                    messages.error(request, str(exc))
                    return redirect("educacao:matriz_modelos")

                if not modelo_importado:
                    messages.error(request, "Arquivo sem linhas válidas para importação.")
                    return redirect("educacao:matriz_modelos")

                resumo = aplicar_modelo_importado_para_unidades(
                    modelo_importado=modelo_importado,
                    ano_referencia=import_form.cleaned_data["ano_referencia"],
                    unidades=unidades,
                    sobrescrever_existentes=bool(import_form.cleaned_data.get("sobrescrever_existentes")),
                )
                messages.success(
                    request,
                    (
                        f"Modelo CSV aplicado em {len(unidades)} unidade(s). "
                        f"Matrizes criadas: {resumo.matrizes_criadas}, "
                        f"atualizadas: {resumo.matrizes_atualizadas}, "
                        f"ignoradas: {resumo.matrizes_ignoradas}, "
                        f"componentes novos: {resumo.componentes_criados}, "
                        f"componentes atualizados: {resumo.componentes_atualizados}."
                    ),
                )
                return redirect("educacao:matriz_modelos")
            messages.error(request, "Corrija os erros do formulário de importação CSV.")

    return render(
        request,
        "educacao/matriz_modelos.html",
        {
            "oficiais_form": oficiais_form,
            "import_form": import_form,
            "actions": [
                {
                    "label": "Voltar para Matrizes",
                    "url": reverse("educacao:matriz_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("educacao.manage")
def matriz_create(request):
    form = MatrizCurricularForm(request.POST or None, user=request.user)
    comp_form = MatrizComponenteForm(request.POST or None, prefix="componente")

    if request.method == "POST":
        wants_first_component = bool((request.POST.get("componente-componente") or "").strip())
        comp_ok = (not wants_first_component) or comp_form.is_valid()

        if form.is_valid() and comp_ok:
            matriz = form.save()
            if wants_first_component:
                mc = comp_form.save(commit=False)
                mc.matriz = matriz
                mc.save()
            messages.success(request, "Matriz curricular cadastrada com sucesso.")
            return redirect("educacao:matriz_update", pk=matriz.pk)
        if wants_first_component and not comp_ok:
            messages.error(request, "Corrija os erros do primeiro componente da matriz.")
        elif not form.is_valid():
            messages.error(request, "Corrija os erros da matriz curricular.")

    return render(
        request,
        "educacao/matriz_form.html",
        {
            "form": form,
            "componente_form": comp_form,
            "mode": "create",
            "cancel_url": reverse("educacao:matriz_list"),
            "submit_label": "Salvar matriz",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:matriz_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("educacao.manage")
def matriz_update(request, pk: int):
    matriz = _resolver_matriz_com_escopo(request, pk)
    if not matriz:
        messages.error(request, "Você não tem acesso a esta matriz.")
        return redirect("educacao:matriz_list")

    form = MatrizCurricularForm(request.POST or None, instance=matriz, user=request.user)
    comp_form = MatrizComponenteForm(request.POST or None, prefix="componente")
    rel_form = MatrizComponenteRelacaoForm(
        request.POST or None,
        prefix="relacao",
        matriz=matriz,
        allow_equivalencia=False,
    )

    if request.method == "POST":
        action = (request.POST.get("_action") or "save_matriz").strip()
        if action == "gerar_componentes_base":
            limpar_existentes = (request.POST.get("limpar_existentes") or "") == "1"
            created, skipped = preencher_componentes_base_matriz(
                matriz,
                limpar_existentes=limpar_existentes,
            )
            if created:
                messages.success(
                    request,
                    f"Componentes base aplicados na matriz: {created} novo(s), {skipped} já existente(s).",
                )
            else:
                messages.info(request, f"Nenhum novo componente adicionado. {skipped} já existente(s).")
            return redirect("educacao:matriz_update", pk=matriz.pk)
        elif action == "clonar_proximo_ano":
            ano_destino_raw = (request.POST.get("ano_destino") or "").strip()
            try:
                ano_destino = int(ano_destino_raw or (int(matriz.ano_referencia) + 1))
                nova_matriz = clonar_matriz_para_ano(matriz, ano_destino=ano_destino)
            except ValueError as exc:
                messages.error(request, str(exc))
                return redirect("educacao:matriz_update", pk=matriz.pk)
            messages.success(
                request,
                f"Matriz clonada para {ano_destino}. Revise e ajuste antes de publicar turmas.",
            )
            return redirect("educacao:matriz_update", pk=nova_matriz.pk)
        elif action == "add_componente":
            if comp_form.is_valid():
                item = comp_form.save(commit=False)
                item.matriz = matriz
                item.save()
                messages.success(request, "Componente adicionado à matriz.")
                return redirect("educacao:matriz_update", pk=matriz.pk)
            messages.error(request, "Corrija os erros do componente.")
        elif action == "add_relacao":
            if rel_form.is_valid():
                relacao = rel_form.save(commit=False)
                relacao.save()
                messages.success(request, "Relação pedagógica adicionada à matriz.")
                return redirect("educacao:matriz_update", pk=matriz.pk)
            messages.error(request, "Corrija os erros da relação pedagógica.")
        elif action == "remove_componente":
            item_id = (request.POST.get("componente_id") or "").strip()
            if item_id.isdigit():
                item = get_object_or_404(MatrizComponente, pk=int(item_id), matriz=matriz)
                item.delete()
                messages.success(request, "Componente removido da matriz.")
            return redirect("educacao:matriz_update", pk=matriz.pk)
        elif action == "remove_relacao":
            item_id = (request.POST.get("relacao_id") or "").strip()
            if item_id.isdigit():
                item = get_object_or_404(
                    MatrizComponenteRelacao.objects.select_related("origem", "destino"),
                    pk=int(item_id),
                    origem__matriz=matriz,
                    destino__matriz=matriz,
                )
                item.delete()
                messages.success(request, "Relação pedagógica removida da matriz.")
            return redirect("educacao:matriz_update", pk=matriz.pk)
        else:
            if form.is_valid():
                form.save()
                messages.success(request, "Matriz curricular atualizada com sucesso.")
                return redirect("educacao:matriz_update", pk=matriz.pk)
            messages.error(request, "Corrija os erros da matriz curricular.")

    componentes = matriz.componentes.select_related("componente").order_by("ordem", "componente__nome")
    relacoes = (
        MatrizComponenteRelacao.objects.select_related(
            "origem",
            "origem__componente",
            "destino",
            "destino__componente",
        )
        .filter(origem__matriz=matriz, destino__matriz=matriz)
        .exclude(tipo=MatrizComponenteRelacao.Tipo.EQUIVALENCIA)
        .order_by("tipo", "origem__ordem", "destino__ordem")
    )

    return render(
        request,
        "educacao/matriz_form.html",
        {
            "form": form,
            "componente_form": comp_form,
            "relacao_form": rel_form,
            "componentes": componentes,
            "relacoes": relacoes,
            "mode": "update",
            "matriz": matriz,
            "next_year_default": int(matriz.ano_referencia) + 1,
            "cancel_url": reverse("educacao:matriz_list"),
            "submit_label": "Atualizar matriz",
            "actions": [
                {
                    "label": "Equivalências",
                    "url": reverse("educacao:matriz_equivalencias", args=[matriz.pk]),
                    "icon": "fa-solid fa-network-wired",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Consistência",
                    "url": reverse("educacao:matriz_consistencia", args=[matriz.pk]),
                    "icon": "fa-solid fa-ruler-combined",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Voltar",
                    "url": reverse("educacao:matriz_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("educacao.manage")
def matriz_equivalencias(request, pk: int):
    matriz = _resolver_matriz_com_escopo(request, pk)
    if not matriz:
        messages.error(request, "Você não tem acesso a esta matriz.")
        return redirect("educacao:matriz_list")

    grupo_form = MatrizEquivalenciaGrupoForm(request.POST or None, prefix="grupo")
    selected_grupo_id = (request.POST.get("grupo_id") or "").strip()
    selected_grupo = None
    if selected_grupo_id.isdigit():
        selected_grupo = MatrizComponenteEquivalenciaGrupo.objects.filter(
            pk=int(selected_grupo_id),
            matriz=matriz,
        ).first()
    item_form = MatrizEquivalenciaItemForm(
        request.POST or None,
        prefix="item",
        matriz=matriz,
        grupo=selected_grupo,
    )

    if request.method == "POST":
        action = (request.POST.get("_action") or "").strip()

        if action == "add_grupo":
            if grupo_form.is_valid():
                grupo = grupo_form.save(commit=False)
                grupo.matriz = matriz
                grupo.save()
                messages.success(request, "Grupo de equivalência adicionado.")
                return redirect("educacao:matriz_equivalencias", pk=matriz.pk)
            messages.error(request, "Corrija os erros do grupo de equivalência.")

        elif action == "remove_grupo":
            grupo_id = (request.POST.get("grupo_id") or "").strip()
            if grupo_id.isdigit():
                grupo = get_object_or_404(
                    MatrizComponenteEquivalenciaGrupo,
                    pk=int(grupo_id),
                    matriz=matriz,
                )
                grupo.delete()
                messages.success(request, "Grupo de equivalência removido.")
            return redirect("educacao:matriz_equivalencias", pk=matriz.pk)

        elif action == "add_item":
            grupo_id = (request.POST.get("grupo_id") or "").strip()
            grupo = None
            if grupo_id.isdigit():
                grupo = MatrizComponenteEquivalenciaGrupo.objects.filter(
                    pk=int(grupo_id),
                    matriz=matriz,
                ).first()
            if not grupo:
                messages.error(request, "Selecione o grupo de equivalência para adicionar o componente.")
                return redirect("educacao:matriz_equivalencias", pk=matriz.pk)

            item_form = MatrizEquivalenciaItemForm(request.POST, prefix="item", matriz=matriz, grupo=grupo)
            if item_form.is_valid():
                item = item_form.save(commit=False)
                item.grupo = grupo
                item.save()
                messages.success(request, "Componente vinculado ao grupo de equivalência.")
                return redirect("educacao:matriz_equivalencias", pk=matriz.pk)
            selected_grupo = grupo
            messages.error(request, "Corrija os erros do item de equivalência.")

        elif action == "remove_item":
            item_id = (request.POST.get("item_id") or "").strip()
            if item_id.isdigit():
                item = get_object_or_404(
                    MatrizComponenteEquivalenciaItem.objects.select_related("grupo"),
                    pk=int(item_id),
                    grupo__matriz=matriz,
                )
                item.delete()
                messages.success(request, "Componente removido do grupo.")
            return redirect("educacao:matriz_equivalencias", pk=matriz.pk)

    grupos = (
        MatrizComponenteEquivalenciaGrupo.objects.filter(matriz=matriz)
        .prefetch_related(
            "itens",
            "itens__componente",
            "itens__componente__componente",
        )
        .order_by("nome")
    )

    return render(
        request,
        "educacao/matriz_equivalencias.html",
        {
            "matriz": matriz,
            "grupos": grupos,
            "grupo_form": grupo_form,
            "item_form": item_form,
            "selected_grupo_id": selected_grupo.pk if selected_grupo else "",
            "actions": [
                {
                    "label": "Consistência",
                    "url": reverse("educacao:matriz_consistencia", args=[matriz.pk]),
                    "icon": "fa-solid fa-ruler-combined",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Voltar para Matriz",
                    "url": reverse("educacao:matriz_update", args=[matriz.pk]),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("educacao.view")
def matriz_consistencia(request, pk: int):
    matriz = _resolver_matriz_com_escopo(request, pk)
    if not matriz:
        messages.error(request, "Você não tem acesso a esta matriz.")
        return redirect("educacao:matriz_list")

    componentes = list(
        matriz.componentes.select_related("componente")
        .order_by("ordem", "componente__nome")
    )
    total_componentes = len(componentes)
    total_ativos = sum(1 for c in componentes if c.ativo)
    total_obrigatorios = sum(1 for c in componentes if c.ativo and c.obrigatoria)
    ch_distribuida = sum((c.carga_horaria_anual or 0) for c in componentes if c.ativo)
    ch_esperada = int(matriz.carga_horaria_anual or 0)
    cobertura = round((ch_distribuida / ch_esperada) * 100, 1) if ch_esperada else 0.0
    saldo = ch_distribuida - ch_esperada
    deficit = abs(saldo) if saldo < 0 else 0
    excesso = saldo if saldo > 0 else 0
    aulas_semanais = sum((c.aulas_semanais or 0) for c in componentes if c.ativo)

    rows = []
    for item in componentes:
        inconsistencias: list[str] = []
        if item.ativo and (item.carga_horaria_anual or 0) == 0:
            inconsistencias.append("Sem carga horária anual")
        if item.ativo and (item.aulas_semanais or 0) == 0:
            inconsistencias.append("Sem aulas semanais")

        rows.append(
            {
                "cells": [
                    {"text": str(item.ordem)},
                    {"text": item.componente.nome},
                    {"text": "Sim" if item.obrigatoria else "Não"},
                    {"text": "Sim" if item.ativo else "Não"},
                    {"text": str(item.carga_horaria_anual or 0)},
                    {"text": str(item.aulas_semanais or 0)},
                    {"text": ", ".join(inconsistencias) if inconsistencias else "OK"},
                ],
            }
        )

    export = (request.GET.get("export") or "").strip().lower()
    if export in {"csv", "pdf"}:
        headers = [
            "Ordem",
            "Componente",
            "Obrigatória",
            "Ativa",
            "CH Anual",
            "Aulas/Semana",
            "Consistência",
        ]
        rows_export = [
            [
                str(item.ordem),
                item.componente.nome,
                "Sim" if item.obrigatoria else "Não",
                "Sim" if item.ativo else "Não",
                str(item.carga_horaria_anual or 0),
                str(item.aulas_semanais or 0),
                ("Sem carga horária anual" if item.ativo and (item.carga_horaria_anual or 0) == 0 else "")
                + (
                    " | Sem aulas semanais"
                    if item.ativo and (item.aulas_semanais or 0) == 0
                    else ""
                )
                or "OK",
            ]
            for item in componentes
        ]
        if export == "csv":
            return export_csv(
                f"matriz_consistencia_{matriz.pk}.csv",
                headers,
                rows_export,
            )
        filtros = (
            f"Matriz={matriz.nome} | CH esperada={ch_esperada}h | CH distribuída={ch_distribuida}h | "
            f"Cobertura={cobertura}%"
        )
        return export_pdf_table(
            request,
            filename=f"matriz_consistencia_{matriz.pk}.pdf",
            title="Relatório de Consistência da Matriz",
            headers=headers,
            rows=rows_export,
            filtros=filtros,
        )

    return render(
        request,
        "educacao/matriz_consistencia.html",
        {
            "matriz": matriz,
            "total_componentes": total_componentes,
            "total_ativos": total_ativos,
            "total_obrigatorios": total_obrigatorios,
            "ch_esperada": ch_esperada,
            "ch_distribuida": ch_distribuida,
            "cobertura": cobertura,
            "deficit": deficit,
            "excesso": excesso,
            "aulas_semanais": aulas_semanais,
            "headers": [
                {"label": "Ordem", "width": "90px"},
                {"label": "Componente"},
                {"label": "Obrigatória", "width": "130px"},
                {"label": "Ativa", "width": "100px"},
                {"label": "CH Anual", "width": "130px"},
                {"label": "Aulas/Semana", "width": "130px"},
                {"label": "Consistência"},
            ],
            "rows": rows,
            "actions": [
                {
                    "label": "Exportar CSV",
                    "url": reverse("educacao:matriz_consistencia", args=[matriz.pk]) + "?export=csv",
                    "icon": "fa-solid fa-file-csv",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Exportar PDF",
                    "url": reverse("educacao:matriz_consistencia", args=[matriz.pk]) + "?export=pdf",
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Equivalências",
                    "url": reverse("educacao:matriz_equivalencias", args=[matriz.pk]),
                    "icon": "fa-solid fa-network-wired",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Voltar para Matriz",
                    "url": reverse("educacao:matriz_update", args=[matriz.pk]),
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

    modalidades_options = format_html_join(
        "",
        '<option value="{}"{}>{}</option>',
        (
            (value, " selected" if modalidade == value else "", label)
            for value, label in CoordenacaoEnsino._meta.get_field("modalidade").choices
        ),
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

    extra_filters = str(
        format_html(
            (
                '<div class="filter-bar__field"><label class="small">Modalidade</label><select name="modalidade">'
                '<option value="">Todas</option>{}</select></div>'
            ),
            modalidades_options,
        )
    )

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
