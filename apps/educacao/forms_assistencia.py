from django import forms

from apps.org.models import Unidade

from .models_assistencia import (
    CardapioEscolar,
    RegistroRefeicaoEscolar,
    RegistroTransporteEscolar,
    RotaTransporteEscolar,
)


class _BaseUnidadeEducacaoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "unidade" in self.fields:
            self.fields["unidade"].queryset = Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO, ativo=True).order_by("nome")


class CardapioEscolarForm(_BaseUnidadeEducacaoForm):
    class Meta:
        model = CardapioEscolar
        fields = ["unidade", "data", "turno", "descricao", "observacao", "ativo"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}),
            "descricao": forms.Textarea(attrs={"rows": 3}),
            "observacao": forms.Textarea(attrs={"rows": 2}),
        }


class RegistroRefeicaoEscolarForm(_BaseUnidadeEducacaoForm):
    class Meta:
        model = RegistroRefeicaoEscolar
        fields = ["unidade", "data", "turno", "total_servidas", "observacao"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}),
            "observacao": forms.Textarea(attrs={"rows": 2}),
        }


class RotaTransporteEscolarForm(_BaseUnidadeEducacaoForm):
    class Meta:
        model = RotaTransporteEscolar
        fields = ["unidade", "nome", "turno", "veiculo", "motorista", "ativo"]


class RegistroTransporteEscolarForm(forms.ModelForm):
    class Meta:
        model = RegistroTransporteEscolar
        fields = ["data", "rota", "total_previsto", "total_transportados", "observacao"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}),
            "observacao": forms.Textarea(attrs={"rows": 2}),
        }
