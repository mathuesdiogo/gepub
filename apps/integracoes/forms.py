from __future__ import annotations

from django import forms

from .models import ConectorIntegracao, IntegracaoExecucao


class ConectorIntegracaoForm(forms.ModelForm):
    class Meta:
        model = ConectorIntegracao
        fields = ["nome", "dominio", "tipo", "endpoint", "credenciais", "configuracao", "ativo"]


class IntegracaoExecucaoForm(forms.ModelForm):
    class Meta:
        model = IntegracaoExecucao
        fields = ["conector", "direcao", "status", "referencia", "quantidade_registros", "detalhes"]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["conector"].queryset = self.fields["conector"].queryset.filter(municipio=municipio, ativo=True)
