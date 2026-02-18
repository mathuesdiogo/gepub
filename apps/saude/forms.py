from django import forms
from apps.org.models import Unidade

class UnidadeSaudeForm(forms.ModelForm):
    class Meta:
        model = Unidade
        fields = ["nome", "secretaria", "endereco", "telefone", "ativo"]  # ajuste se seu model tiver campos diferentes
