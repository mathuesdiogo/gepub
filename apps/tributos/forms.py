from __future__ import annotations

from django import forms

from apps.org.services.cadastros_base import aplicar_sugestoes_em_campo, mapear_sugestoes_por_categoria

from .models import TributoLancamento, TributosCadastro


class TributosCadastroForm(forms.ModelForm):
    class Meta:
        model = TributosCadastro
        fields = [
            "secretaria",
            "unidade",
            "setor",
            "codigo",
            "nome",
            "tipo_pessoa",
            "documento",
            "inscricao_municipal",
            "endereco",
            "email",
            "telefone",
            "status",
            "observacao",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["secretaria"].queryset = self.fields["secretaria"].queryset.filter(municipio=municipio)
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(secretaria__municipio=municipio)
            self.fields["setor"].queryset = self.fields["setor"].queryset.filter(unidade__secretaria__municipio=municipio)


class TributoLancamentoForm(forms.ModelForm):
    class Meta:
        model = TributoLancamento
        fields = [
            "contribuinte",
            "tipo_tributo",
            "exercicio",
            "competencia",
            "referencia",
            "valor_principal",
            "multa",
            "juros",
            "desconto",
            "data_vencimento",
            "observacao",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["contribuinte"].queryset = TributosCadastro.objects.filter(municipio=municipio, status=TributosCadastro.Status.ATIVO)
            sugestoes = mapear_sugestoes_por_categoria(
                municipio_id=municipio.id,
                categorias=["TRIBUTO_TIPO"],
            )
            aplicar_sugestoes_em_campo(self, "tipo_tributo", sugestoes.get("TRIBUTO_TIPO"))
