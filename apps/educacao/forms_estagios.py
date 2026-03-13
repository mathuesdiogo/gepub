from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model

from apps.core.rbac import is_admin, scope_filter_unidades
from apps.org.models import Unidade

from .models import Aluno, Estagio, Matricula, Turma


class EstagioForm(forms.ModelForm):
    class Meta:
        model = Estagio
        fields = [
            "aluno",
            "matricula",
            "turma",
            "unidade",
            "tipo",
            "situacao",
            "concedente_nome",
            "concedente_cnpj",
            "supervisor_nome",
            "orientador",
            "data_inicio_prevista",
            "data_fim_prevista",
            "data_inicio_real",
            "data_fim_real",
            "carga_horaria_total",
            "carga_horaria_cumprida",
            "equivalencia_solicitada",
            "equivalencia_aprovada",
            "termo_compromisso",
            "relatorio_final",
            "observacao",
            "ativo",
        ]
        widgets = {
            "data_inicio_prevista": forms.DateInput(attrs={"type": "date"}),
            "data_fim_prevista": forms.DateInput(attrs={"type": "date"}),
            "data_inicio_real": forms.DateInput(attrs={"type": "date"}),
            "data_fim_real": forms.DateInput(attrs={"type": "date"}),
            "observacao": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["aluno"].required = False
        self.fields["unidade"].required = False

        unidades_qs = Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO, ativo=True).select_related("secretaria", "secretaria__municipio")
        if user and not is_admin(user):
            unidades_qs = scope_filter_unidades(user, unidades_qs)
        unidades_qs = unidades_qs.order_by("secretaria__nome", "nome")
        self.fields["unidade"].queryset = unidades_qs

        turmas_qs = Turma.objects.select_related("unidade", "unidade__secretaria").filter(unidade__in=unidades_qs).order_by("-ano_letivo", "nome")
        self.fields["turma"].queryset = turmas_qs

        matriculas_qs = Matricula.objects.select_related("aluno", "turma", "turma__unidade").filter(turma__in=turmas_qs).order_by("-id")
        self.fields["matricula"].queryset = matriculas_qs

        alunos_qs = Aluno.objects.filter(matriculas__turma__in=turmas_qs).distinct().order_by("nome")
        self.fields["aluno"].queryset = alunos_qs

        user_model = get_user_model()
        self.fields["orientador"].queryset = user_model.objects.order_by("username")

    def clean(self):
        cleaned = super().clean()

        aluno = cleaned.get("aluno")
        matricula = cleaned.get("matricula")
        turma = cleaned.get("turma")
        unidade = cleaned.get("unidade")

        if matricula and not aluno:
            aluno = matricula.aluno
            cleaned["aluno"] = aluno

        if matricula and not turma:
            turma = matricula.turma
            cleaned["turma"] = turma

        if turma and not unidade:
            unidade = turma.unidade
            cleaned["unidade"] = unidade

        if matricula and not unidade:
            unidade = matricula.turma.unidade
            cleaned["unidade"] = unidade

        if not cleaned.get("aluno"):
            self.add_error("aluno", "Selecione o aluno ou informe uma matrícula vinculada.")
        if not cleaned.get("unidade"):
            self.add_error("unidade", "Selecione a unidade ou informe turma/matrícula vinculada.")

        return cleaned
