from django import forms
from .models import Municipio


class MunicipioForm(forms.ModelForm):
    class Meta:
        model = Municipio
        fields = ["nome", "uf", "ativo"]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: Governador Nunes Freire"}),
            "uf": forms.TextInput(attrs={"placeholder": "Ex.: MA"}),
        }

    def clean_uf(self):
        uf = (self.cleaned_data.get("uf") or "").strip().upper()
        if len(uf) != 2:
            raise forms.ValidationError("UF deve ter 2 letras (ex.: MA).")
        return uf
