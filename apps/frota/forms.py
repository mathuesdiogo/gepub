from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model

from apps.accounts.models import Profile
from apps.org.services.cadastros_base import aplicar_sugestoes_em_campo, mapear_sugestoes_por_categoria

from .models import FrotaAbastecimento, FrotaCadastro, FrotaManutencao, FrotaViagem


User = get_user_model()


class FrotaCadastroForm(forms.ModelForm):
    class Meta:
        model = FrotaCadastro
        fields = [
            "secretaria",
            "unidade",
            "setor",
            "codigo",
            "placa",
            "nome",
            "marca_modelo",
            "ano_fabricacao",
            "combustivel",
            "quilometragem_atual",
            "situacao",
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
                categorias=["COMBUSTIVEL_TIPO"],
            )
            aplicar_sugestoes_em_campo(self, "combustivel", sugestoes.get("COMBUSTIVEL_TIPO"))

    def clean(self):
        cleaned = super().clean()
        placa = (cleaned.get("placa") or "").strip().upper()
        cleaned["placa"] = placa
        return cleaned


class FrotaAbastecimentoForm(forms.ModelForm):
    class Meta:
        model = FrotaAbastecimento
        fields = ["veiculo", "data_abastecimento", "litros", "valor_total", "quilometragem", "posto"]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["veiculo"].queryset = FrotaCadastro.objects.filter(municipio=municipio, status=FrotaCadastro.Status.ATIVO)
            sugestoes = mapear_sugestoes_por_categoria(
                municipio_id=municipio.id,
                categorias=["MANUTENCAO_TIPO"],
            )
            aplicar_sugestoes_em_campo(self, "tipo", sugestoes.get("MANUTENCAO_TIPO"))


class FrotaManutencaoForm(forms.ModelForm):
    class Meta:
        model = FrotaManutencao
        fields = ["veiculo", "tipo", "data_inicio", "data_fim", "oficina", "descricao", "valor_total"]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["veiculo"].queryset = FrotaCadastro.objects.filter(municipio=municipio, status=FrotaCadastro.Status.ATIVO)

    def clean(self):
        cleaned = super().clean()
        inicio = cleaned.get("data_inicio")
        fim = cleaned.get("data_fim")
        if inicio and fim and fim < inicio:
            self.add_error("data_fim", "Data final não pode ser menor que a inicial.")
        return cleaned


class FrotaViagemForm(forms.ModelForm):
    class Meta:
        model = FrotaViagem
        fields = ["veiculo", "motorista", "destino", "finalidade", "data_saida", "data_retorno", "km_saida", "km_retorno"]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["veiculo"].queryset = FrotaCadastro.objects.filter(municipio=municipio, status=FrotaCadastro.Status.ATIVO)
            self.fields["motorista"].queryset = (
                User.objects.filter(profile__municipio=municipio, profile__ativo=True)
                .exclude(profile__role=Profile.Role.ALUNO)
                .order_by("first_name", "username")
            )
            self.fields["motorista"].label_from_instance = lambda obj: (obj.get_full_name() or obj.username).strip()
            sugestoes = mapear_sugestoes_por_categoria(
                municipio_id=municipio.id,
                categorias=["SERVICO_FROTA"],
            )
            aplicar_sugestoes_em_campo(self, "finalidade", sugestoes.get("SERVICO_FROTA"))

    def clean(self):
        cleaned = super().clean()
        saida = cleaned.get("data_saida")
        retorno = cleaned.get("data_retorno")
        km_saida = cleaned.get("km_saida") or 0
        km_retorno = cleaned.get("km_retorno") or 0
        if saida and retorno and retorno < saida:
            self.add_error("data_retorno", "Data de retorno não pode ser menor que a data de saída.")
        if km_retorno and km_retorno < km_saida:
            self.add_error("km_retorno", "KM retorno não pode ser menor que KM saída.")
        return cleaned
