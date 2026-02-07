from django import forms

from .models import Turma, Aluno, Matricula


class TurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = ["unidade", "nome", "ano_letivo", "turno", "ativo"]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: 1º Ano A"}),
            "ano_letivo": forms.NumberInput(attrs={"min": 2000, "max": 2100}),
        }


class AlunoForm(forms.ModelForm):
    class Meta:
        model = Aluno
        fields = [
            "nome",
            "data_nascimento",
            "cpf",
            "nis",
            "nome_mae",
            "nome_pai",
            "telefone",
            "email",
            "endereco",
            "ativo",
        ]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Nome completo"}),
            "data_nascimento": forms.DateInput(attrs={"type": "date"}),
            "cpf": forms.TextInput(attrs={"placeholder": "000.000.000-00 (opcional)"}),
            "nis": forms.TextInput(attrs={"placeholder": "NIS (opcional)"}),
            "nome_mae": forms.TextInput(attrs={"placeholder": "Nome da mãe (opcional)"}),
            "nome_pai": forms.TextInput(attrs={"placeholder": "Nome do pai (opcional)"}),
            "telefone": forms.TextInput(attrs={"placeholder": "(00) 0000-0000"}),
            "email": forms.EmailInput(attrs={"placeholder": "contato@..."}),
            "endereco": forms.Textarea(attrs={"rows": 3, "placeholder": "Endereço (opcional)"}),
        }


class MatriculaForm(forms.ModelForm):
    class Meta:
        model = Matricula
        fields = ["turma", "data_matricula", "situacao", "observacao"]
        widgets = {
            "data_matricula": forms.DateInput(attrs={"type": "date"}),
            "observacao": forms.Textarea(attrs={"rows": 3, "placeholder": "Observação (opcional)"}),
        }
