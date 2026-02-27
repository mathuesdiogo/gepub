from __future__ import annotations

from django import forms

from .models import AditivoContrato, ContratoAdministrativo, MedicaoContrato


class ContratoAdministrativoForm(forms.ModelForm):
    class Meta:
        model = ContratoAdministrativo
        fields = [
            "processo_licitatorio",
            "requisicao_compra",
            "numero",
            "objeto",
            "fornecedor_nome",
            "fornecedor_documento",
            "fiscal_nome",
            "valor_total",
            "vigencia_inicio",
            "vigencia_fim",
            "status",
            "empenho",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["processo_licitatorio"].queryset = self.fields["processo_licitatorio"].queryset.filter(municipio=municipio)
            self.fields["requisicao_compra"].queryset = self.fields["requisicao_compra"].queryset.filter(municipio=municipio)
            self.fields["empenho"].queryset = self.fields["empenho"].queryset.filter(municipio=municipio)


class AditivoContratoForm(forms.ModelForm):
    class Meta:
        model = AditivoContrato
        fields = ["tipo", "numero", "data_ato", "valor_aditivo", "nova_vigencia_fim", "descricao"]


class MedicaoContratoForm(forms.ModelForm):
    class Meta:
        model = MedicaoContrato
        fields = ["numero", "competencia", "data_medicao", "valor_medido", "observacao"]

    def clean_competencia(self):
        value = (self.cleaned_data.get("competencia") or "").strip()
        if len(value) != 7 or value[4] != "-":
            raise forms.ValidationError("Use o formato YYYY-MM para competencia.")
        ano, mes = value.split("-", 1)
        if not (ano.isdigit() and mes.isdigit() and 1 <= int(mes) <= 12):
            raise forms.ValidationError("Competencia invalida.")
        return value
