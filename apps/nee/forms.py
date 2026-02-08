from django import forms
from .models import TipoNecessidade


class TipoNecessidadeForm(forms.ModelForm):
    class Meta:
        model = TipoNecessidade
        fields = ["nome", "ativo"]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: TEA, TDAH, Def. Intelectual..."}),
        }
