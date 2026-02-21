from django import forms
from .models_periodos import PeriodoLetivo


class PeriodoLetivoForm(forms.ModelForm):
    class Meta:
        model = PeriodoLetivo
        fields = ["ano_letivo", "tipo", "numero", "inicio", "fim", "ativo"]

    def clean(self):
        cleaned = super().clean()
        inicio = cleaned.get("inicio")
        fim = cleaned.get("fim")
        if inicio and fim and fim < inicio:
            self.add_error("fim", "A data final não pode ser menor que a data inicial.")
        return cleaned
