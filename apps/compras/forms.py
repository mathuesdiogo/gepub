from __future__ import annotations

from django import forms

from apps.org.services.cadastros_base import aplicar_sugestoes_em_campo, mapear_sugestoes_por_categoria

from .models import ProcessoLicitatorio, RequisicaoCompra, RequisicaoCompraItem


class RequisicaoCompraForm(forms.ModelForm):
    class Meta:
        model = RequisicaoCompra
        fields = [
            "processo",
            "secretaria",
            "unidade",
            "setor",
            "numero",
            "objeto",
            "justificativa",
            "valor_estimado",
            "data_necessidade",
            "status",
            "fornecedor_nome",
            "fornecedor_documento",
            "dotacao",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["processo"].queryset = self.fields["processo"].queryset.filter(municipio=municipio)
            self.fields["secretaria"].queryset = self.fields["secretaria"].queryset.filter(municipio=municipio)
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(secretaria__municipio=municipio)
            self.fields["setor"].queryset = self.fields["setor"].queryset.filter(unidade__secretaria__municipio=municipio)
            self.fields["dotacao"].queryset = self.fields["dotacao"].queryset.filter(municipio=municipio, ativo=True)


class RequisicaoCompraItemForm(forms.ModelForm):
    class Meta:
        model = RequisicaoCompraItem
        fields = ["descricao", "unidade_medida", "quantidade", "valor_unitario"]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            sugestoes = mapear_sugestoes_por_categoria(
                municipio_id=municipio.id,
                categorias=["SERVICO_TIPO", "INSUMO_TIPO"],
            )
            aplicar_sugestoes_em_campo(
                self,
                "descricao",
                (sugestoes.get("SERVICO_TIPO") or []) + (sugestoes.get("INSUMO_TIPO") or []),
            )


class ProcessoLicitatorioForm(forms.ModelForm):
    class Meta:
        model = ProcessoLicitatorio
        fields = [
            "requisicao",
            "numero_processo",
            "modalidade",
            "objeto",
            "status",
            "data_abertura",
            "vencedor_nome",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["requisicao"].queryset = self.fields["requisicao"].queryset.filter(municipio=municipio)
