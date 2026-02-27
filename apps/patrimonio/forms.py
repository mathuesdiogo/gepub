from __future__ import annotations

from django import forms

from apps.org.models import Unidade
from apps.org.services.cadastros_base import aplicar_sugestoes_em_campo, mapear_sugestoes_por_categoria

from .models import PatrimonioCadastro, PatrimonioInventario, PatrimonioMovimentacao


class PatrimonioCadastroForm(forms.ModelForm):
    class Meta:
        model = PatrimonioCadastro
        fields = [
            "secretaria",
            "unidade",
            "setor",
            "codigo",
            "tombo",
            "nome",
            "categoria",
            "situacao",
            "data_aquisicao",
            "valor_aquisicao",
            "estado_conservacao",
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
                categorias=["BEM_CATEGORIA"],
            )
            aplicar_sugestoes_em_campo(self, "categoria", sugestoes.get("BEM_CATEGORIA"))

    def clean(self):
        cleaned = super().clean()
        tombo = (cleaned.get("tombo") or "").strip()
        if not tombo:
            cleaned["tombo"] = (cleaned.get("codigo") or "").strip()
        return cleaned


class PatrimonioMovimentacaoForm(forms.ModelForm):
    class Meta:
        model = PatrimonioMovimentacao
        fields = ["bem", "tipo", "data_movimento", "unidade_origem", "unidade_destino", "valor_movimento", "observacao"]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["bem"].queryset = PatrimonioCadastro.objects.filter(municipio=municipio, status=PatrimonioCadastro.Status.ATIVO)
            unidades = Unidade.objects.filter(secretaria__municipio=municipio, ativo=True)
            self.fields["unidade_origem"].queryset = unidades
            self.fields["unidade_destino"].queryset = unidades

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo")
        origem = cleaned.get("unidade_origem")
        destino = cleaned.get("unidade_destino")
        if tipo == PatrimonioMovimentacao.Tipo.TRANSFERENCIA and (not origem or not destino):
            self.add_error("unidade_destino", "Transferência exige unidade de origem e destino.")
        if origem and destino and origem.pk == destino.pk:
            self.add_error("unidade_destino", "Origem e destino devem ser diferentes.")
        return cleaned


class PatrimonioInventarioForm(forms.ModelForm):
    class Meta:
        model = PatrimonioInventario
        fields = ["codigo", "referencia", "unidade", "observacao"]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["unidade"].queryset = Unidade.objects.filter(secretaria__municipio=municipio, ativo=True)
