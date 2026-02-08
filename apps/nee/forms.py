from django import forms
from .models import TipoNecessidade
from .models import AlunoNecessidade


class TipoNecessidadeForm(forms.ModelForm):
    class Meta:
        model = TipoNecessidade
        fields = ["nome", "ativo"]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: TEA, TDAH, Def. Intelectual..."}),
        }
class AlunoNecessidadeForm(forms.ModelForm):
    class Meta:
        model = AlunoNecessidade
        fields = ["tipo", "cid", "observacao", "ativo"]
        widgets = {
            "cid": forms.TextInput(attrs={"placeholder": "Ex.: F84.0 (opcional)"}),
            "observacao": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Observações (opcional)"}
            ),
        }
