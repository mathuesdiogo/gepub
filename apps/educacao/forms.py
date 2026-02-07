from django import forms
from .models import Turma


class TurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = ["unidade", "nome", "ano_letivo", "turno", "ativo"]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: 1º Ano A"}),
            "ano_letivo": forms.NumberInput(attrs={"min": 2000, "max": 2100}),
        }
