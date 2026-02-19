from django import forms
from .models_diario import Avaliacao


class AvaliacaoForm(forms.ModelForm):
    class Meta:
        model = Avaliacao
        fields = ["titulo", "peso", "data"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}),
        }
