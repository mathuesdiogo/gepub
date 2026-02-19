from django import forms
from .models_horarios import HorarioAula


class HorarioAulaForm(forms.ModelForm):
    class Meta:
        model = HorarioAula
        fields = ["dia_semana", "ordem", "inicio", "fim", "componente", "local", "professor", "ativo"]

    def clean(self):
        cleaned = super().clean()
        ini = cleaned.get("inicio")
        fim = cleaned.get("fim")
        if ini and fim and fim <= ini:
            self.add_error("fim", "A hora final deve ser maior que a hora inicial.")
        return cleaned
