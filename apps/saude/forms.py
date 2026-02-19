from django import forms

from apps.org.models import Unidade
from .models import ProfissionalSaude, AtendimentoSaude


class UnidadeSaudeForm(forms.ModelForm):
    class Meta:
        model = Unidade
        fields = ["nome", "secretaria", "telefone", "email", "endereco", "ativo"]


class ProfissionalSaudeForm(forms.ModelForm):
    class Meta:
        model = ProfissionalSaude
        fields = ["nome", "unidade", "cargo", "cpf", "telefone", "email", "ativo"]


class AtendimentoSaudeForm(forms.ModelForm):
    class Meta:
        model = AtendimentoSaude
        fields = ["unidade", "profissional", "data", "tipo", "paciente_nome", "paciente_cpf", "observacoes",]

    def __init__(self, *args, **kwargs):
        unidades_qs = kwargs.pop("unidades_qs", None)
        profissionais_qs = kwargs.pop("profissionais_qs", None)
        super().__init__(*args, **kwargs)

        if unidades_qs is not None and "unidade" in self.fields:
            self.fields["unidade"].queryset = unidades_qs

        if profissionais_qs is not None and "profissional" in self.fields:
            self.fields["profissional"].queryset = profissionais_qs
