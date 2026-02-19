from django import forms
from .models_diario import Aula


class AulaForm(forms.ModelForm):
    class Meta:
        model = Aula
        fields = ["data", "conteudo", "observacoes"]
