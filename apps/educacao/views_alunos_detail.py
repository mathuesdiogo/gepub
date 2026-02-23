from __future__ import annotations

from django import forms
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import can

from .models import Aluno, Matricula, Turma

from apps.nee.models import AlunoNecessidade, TipoNecessidade, ApoioMatricula

try:
    from apps.saude.models import AtendimentoSaude
except Exception:  # pragma: no cover
    AtendimentoSaude = None  # type: ignore


def _matricula_form_fields():
    names = {f.name for f in Matricula._meta.fields}
    fields = ["turma"]
    # se existir (em alguns projetos você usa situacao)
    if "situacao" in names:
        fields.append("situacao")
    if "ativo" in names:
        fields.append("ativo")
    return fields


class MatriculaInlineForm(forms.ModelForm):
    class Meta:
        model = Matricula
        fields = _matricula_form_fields()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Turmas ativas primeiro (se existir campo ativo)
        qs = Turma.objects.all().order_by("-ano_letivo", "nome")
        if "ativo" in {f.name for f in Turma._meta.fields}:
            qs = Turma.objects.filter(ativo=True).order_by("-ano_letivo", "nome")
        if "turma" in self.fields:
            self.fields["turma"].queryset = qs


class NeeInlineForm(forms.ModelForm):
    class Meta:
        model = AlunoNecessidade
        fields = ["tipo", "observacao"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tipo"].queryset = TipoNecessidade.objects.filter(ativo=True).order_by("nome")


class ApoioInlineForm(forms.ModelForm):
    class Meta:
        model = ApoioMatricula
        fields = ["matricula", "descricao", "observacao", "ativo"]

    def __init__(self, aluno: Aluno, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["matricula"].queryset = Matricula.objects.select_related("turma", "turma__unidade").filter(aluno=aluno).order_by("-id")


@method_decorator(login_required, name="dispatch")
@method_decorator(require_perm("educacao.view"), name="dispatch")
class AlunoDetailView(View):
    template_name = "educacao/aluno_detail.html"

    def _build_context(self, request, aluno: Aluno, form_matricula=None, form_nee=None, form_apoio=None):
        matriculas = (
            Matricula.objects
            .select_related("turma", "turma__unidade", "turma__unidade__secretaria", "turma__unidade__secretaria__municipio")
            .filter(aluno=aluno)
            .order_by("-id")
        )

        headers_matriculas = [
            {"label": "Turma"},
            {"label": "Ano", "width": "120px"},
            {"label": "Turno", "width": "140px"},
            {"label": "Unidade"},
            {"label": "Situação", "width": "160px"},
        ]

        rows_matriculas = []
        for m in matriculas:
            turma = m.turma
            unidade = getattr(turma, "unidade", None)
            unidade_nome = getattr(unidade, "nome", "—")
            situacao = getattr(m, "get_situacao_display", None)
            situacao_txt = situacao() if callable(situacao) else getattr(m, "situacao", "—")
            rows_matriculas.append({
                "cells": [
                    {"text": turma.nome, "url": reverse("educacao:turma_detail", args=[turma.pk])},
                    {"text": str(getattr(turma, "ano_letivo", "") or "—")},
                    {"text": getattr(turma, "get_turno_display", lambda: getattr(turma, "turno", "—"))()},
                    {"text": unidade_nome},
                    {"text": situacao_txt},
                ],
                "can_edit": False,
                "edit_url": "",
            })

        fields = [
            ("CPF", getattr(aluno, "cpf", "") or "—"),
            ("NIS", getattr(aluno, "nis", "") or "—"),
            ("Data nascimento", aluno.data_nascimento.strftime("%d/%m/%Y") if getattr(aluno, "data_nascimento", None) else "—"),
            ("Telefone", getattr(aluno, "telefone", "") or "—"),
            ("E-mail", getattr(aluno, "email", "") or "—"),
            ("Ativo", "Sim" if getattr(aluno, "ativo", True) else "Não"),
        ]
        pills = [("Matrículas", matriculas.count())]

        necessidades = AlunoNecessidade.objects.select_related("tipo").filter(aluno=aluno).order_by("-id")
        apoios = ApoioMatricula.objects.select_related("matricula", "matricula__turma", "matricula__turma__unidade").filter(matricula__aluno=aluno).order_by("-id")

        can_edu_manage = can(request.user, "educacao.manage") or can(request.user, "nee.manage")

        return {
            "aluno": aluno,
            "fields": fields,
            "pills": pills,
            "headers_matriculas": headers_matriculas,
            "rows_matriculas": rows_matriculas,
            "can_edu_manage": can_edu_manage,
            "necessidades": necessidades,
            "apoios": apoios,
            "form_matricula": form_matricula or MatriculaInlineForm(),
            "form_nee": form_nee or NeeInlineForm(),
            "form_apoio": form_apoio or ApoioInlineForm(aluno),
        }

    def get(self, request, pk: int):
        aluno = get_object_or_404(Aluno, pk=pk)
        return render(request, self.template_name, self._build_context(request, aluno))

    def post(self, request, pk: int):
        aluno = get_object_or_404(Aluno, pk=pk)
        action = (request.POST.get("_action") or "").strip()

        if not (can(request.user, "educacao.manage") or can(request.user, "nee.manage")):
            return redirect("educacao:aluno_detail", pk=aluno.pk)

        # default forms
        form_matricula = MatriculaInlineForm(request.POST or None)
        form_nee = NeeInlineForm(request.POST or None)
        form_apoio = ApoioInlineForm(aluno, request.POST or None)

        if action == "add_matricula":
            if form_matricula.is_valid():
                obj = form_matricula.save(commit=False)
                obj.aluno = aluno
                obj.save()
                return redirect("educacao:aluno_detail", pk=aluno.pk)

        elif action == "add_nee":
            if form_nee.is_valid():
                obj = form_nee.save(commit=False)
                obj.aluno = aluno
                obj.save()
                return redirect("educacao:aluno_detail", pk=aluno.pk)

        elif action == "add_apoio":
            if form_apoio.is_valid():
                form_apoio.save()
                return redirect("educacao:aluno_detail", pk=aluno.pk)

        # se falhar validação, renderiza de volta com erros
        ctx = self._build_context(request, aluno, form_matricula=form_matricula, form_nee=form_nee, form_apoio=form_apoio)
        return render(request, self.template_name, ctx)
