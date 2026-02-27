from django import forms

from .models_periodos import FechamentoPeriodoTurma


class FechamentoPeriodoTurmaForm(forms.ModelForm):
    class Meta:
        model = FechamentoPeriodoTurma
        fields = [
            "media_corte",
            "frequencia_corte",
            "observacao",
        ]
        widgets = {
            "observacao": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        media_corte = cleaned.get("media_corte")
        frequencia_corte = cleaned.get("frequencia_corte")

        if media_corte is not None and media_corte <= 0:
            self.add_error("media_corte", "A média de corte deve ser maior que zero.")
        if frequencia_corte is not None and (frequencia_corte < 0 or frequencia_corte > 100):
            self.add_error("frequencia_corte", "A frequência de corte deve estar entre 0 e 100.")
        return cleaned
