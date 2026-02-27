from __future__ import annotations

from decimal import Decimal

from django import forms

from apps.org.models import Secretaria, Setor, Unidade
from apps.org.services.cadastros_base import aplicar_sugestoes_em_campo, mapear_sugestoes_por_categoria

from .models import AlmoxarifadoCadastro, AlmoxarifadoMovimento, AlmoxarifadoRequisicao


class AlmoxarifadoCadastroForm(forms.ModelForm):
    class Meta:
        model = AlmoxarifadoCadastro
        fields = [
            "secretaria",
            "unidade",
            "setor",
            "codigo",
            "nome",
            "unidade_medida",
            "estoque_minimo",
            "saldo_atual",
            "valor_medio",
            "status",
            "observacao",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["secretaria"].queryset = self.fields["secretaria"].queryset.filter(municipio=municipio)
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(secretaria__municipio=municipio)
            self.fields["setor"].queryset = self.fields["setor"].queryset.filter(unidade__secretaria__municipio=municipio)
            sugestoes = mapear_sugestoes_por_categoria(
                municipio_id=municipio.id,
                categorias=["INSUMO_TIPO"],
            )
            aplicar_sugestoes_em_campo(self, "nome", sugestoes.get("INSUMO_TIPO"))


class AlmoxarifadoMovimentoForm(forms.ModelForm):
    class Meta:
        model = AlmoxarifadoMovimento
        fields = ["item", "tipo", "data_movimento", "quantidade", "valor_unitario", "documento", "observacao"]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["item"].queryset = AlmoxarifadoCadastro.objects.filter(municipio=municipio, status=AlmoxarifadoCadastro.Status.ATIVO)

    def clean(self):
        cleaned = super().clean()
        qtd = cleaned.get("quantidade") or Decimal("0")
        if qtd <= 0:
            self.add_error("quantidade", "Quantidade deve ser maior que zero.")
        return cleaned


class AlmoxarifadoRequisicaoForm(forms.ModelForm):
    class Meta:
        model = AlmoxarifadoRequisicao
        fields = [
            "numero",
            "item",
            "secretaria_solicitante",
            "unidade_solicitante",
            "setor_solicitante",
            "quantidade",
            "justificativa",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.municipio = municipio
        if municipio is not None:
            self.fields["item"].queryset = AlmoxarifadoCadastro.objects.filter(municipio=municipio, status=AlmoxarifadoCadastro.Status.ATIVO)
            self.fields["secretaria_solicitante"].queryset = Secretaria.objects.filter(municipio=municipio, ativo=True)
            self.fields["unidade_solicitante"].queryset = Unidade.objects.filter(secretaria__municipio=municipio, ativo=True)
            self.fields["setor_solicitante"].queryset = Setor.objects.filter(unidade__secretaria__municipio=municipio, ativo=True)

    def clean(self):
        cleaned = super().clean()
        unidade = cleaned.get("unidade_solicitante")
        setor = cleaned.get("setor_solicitante")
        qtd = cleaned.get("quantidade") or Decimal("0")
        if qtd <= 0:
            self.add_error("quantidade", "Quantidade deve ser maior que zero.")
        if setor and unidade and setor.unidade_id != unidade.id:
            self.add_error("setor_solicitante", "Setor solicitante deve pertencer à unidade solicitante.")
        return cleaned
