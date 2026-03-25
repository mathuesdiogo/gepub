from __future__ import annotations

from django import forms

from apps.org.models import Unidade, LocalEstrutural, Secretaria
from apps.org.services.cadastros_base import aplicar_sugestoes_em_campo, mapear_sugestoes_por_categoria

from .models import PatrimonioCadastro, PatrimonioInventario, PatrimonioMovimentacao


class PatrimonioCadastroForm(forms.ModelForm):
    class Meta:
        model = PatrimonioCadastro
        fields = [
            "secretaria",
            "unidade",
            "setor",
            "local_estrutural",
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
            self.fields["local_estrutural"].queryset = LocalEstrutural.objects.filter(
                municipio=municipio,
                status=LocalEstrutural.Status.ATIVO,
            ).order_by("nome")
            sugestoes = mapear_sugestoes_por_categoria(
                municipio_id=municipio.id,
                categorias=["BEM_CATEGORIA"],
            )
            aplicar_sugestoes_em_campo(self, "categoria", sugestoes.get("BEM_CATEGORIA"))

    def clean(self):
        cleaned = super().clean()
        tombo = (cleaned.get("tombo") or "").strip()
        unidade = cleaned.get("unidade")
        local = cleaned.get("local_estrutural")
        if not tombo:
            cleaned["tombo"] = (cleaned.get("codigo") or "").strip()
        if local and unidade and local.unidade_id != unidade.id:
            self.add_error("local_estrutural", "Local estrutural deve pertencer à unidade selecionada.")
        return cleaned


class PatrimonioMovimentacaoForm(forms.ModelForm):
    class Meta:
        model = PatrimonioMovimentacao
        fields = [
            "bem",
            "tipo",
            "data_movimento",
            "unidade_origem",
            "unidade_destino",
            "local_origem",
            "local_destino",
            "valor_movimento",
            "observacao",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["bem"].queryset = PatrimonioCadastro.objects.filter(municipio=municipio, status=PatrimonioCadastro.Status.ATIVO)
            unidades = Unidade.objects.filter(secretaria__municipio=municipio, ativo=True)
            self.fields["unidade_origem"].queryset = unidades
            self.fields["unidade_destino"].queryset = unidades
            locais = LocalEstrutural.objects.filter(municipio=municipio, status=LocalEstrutural.Status.ATIVO)
            self.fields["local_origem"].queryset = locais
            self.fields["local_destino"].queryset = locais

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo")
        origem = cleaned.get("unidade_origem")
        destino = cleaned.get("unidade_destino")
        local_origem = cleaned.get("local_origem")
        local_destino = cleaned.get("local_destino")
        if tipo == PatrimonioMovimentacao.Tipo.TRANSFERENCIA and (not origem or not destino):
            self.add_error("unidade_destino", "Transferência exige unidade de origem e destino.")
        if origem and destino and origem.pk == destino.pk:
            self.add_error("unidade_destino", "Origem e destino devem ser diferentes.")
        if local_origem and origem and local_origem.unidade_id != origem.id:
            self.add_error("local_origem", "Local de origem deve pertencer à unidade de origem.")
        if local_destino and destino and local_destino.unidade_id != destino.id:
            self.add_error("local_destino", "Local de destino deve pertencer à unidade de destino.")
        return cleaned


class PatrimonioInventarioForm(forms.ModelForm):
    class Meta:
        model = PatrimonioInventario
        fields = ["codigo", "referencia", "secretaria", "unidade", "local_estrutural", "observacao"]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["secretaria"].queryset = Secretaria.objects.filter(municipio=municipio, ativo=True)
            self.fields["unidade"].queryset = Unidade.objects.filter(secretaria__municipio=municipio, ativo=True)
            self.fields["local_estrutural"].queryset = LocalEstrutural.objects.filter(
                municipio=municipio,
                status=LocalEstrutural.Status.ATIVO,
            )

    def clean(self):
        cleaned = super().clean()
        secretaria = cleaned.get("secretaria")
        unidade = cleaned.get("unidade")
        local = cleaned.get("local_estrutural")
        if unidade and secretaria and unidade.secretaria_id != secretaria.id:
            self.add_error("unidade", "A unidade deve pertencer à secretaria selecionada.")
        if local and unidade and local.unidade_id != unidade.id:
            self.add_error("local_estrutural", "O local estrutural deve pertencer à unidade selecionada.")
        return cleaned
