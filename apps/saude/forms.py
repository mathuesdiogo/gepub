from django import forms

from apps.educacao.models import Aluno
from apps.org.models import Unidade
from .models import ProfissionalSaude, AtendimentoSaude


class UnidadeSaudeForm(forms.ModelForm):
    """
    Form de Unidade (org.Unidade) usado em views_unidades.py.
    IMPORTANTe: views_unidades força obj.tipo = Unidade.Tipo.SAUDE no save,
    então aqui não expomos o campo 'tipo' no formulário.
    """
    class Meta:
        model = Unidade
        fields = [
            "nome",
                  # se não existir no seu model, remova
            "codigo_inep",
            "cnpj",
            "telefone",
            "email",
            "endereco",
            "ativo",
            "secretaria",
        ]


class ProfissionalSaudeForm(forms.ModelForm):
    class Meta:
        model = ProfissionalSaude
        fields = ["nome", "unidade", "cargo", "cpf", "telefone", "email", "ativo"]


class AtendimentoSaudeForm(forms.ModelForm):
    class Meta:
        model = AtendimentoSaude
        fields = [
            "aluno",
            "unidade",
            "profissional",
            "data",
            "tipo",
            "cid",
            "observacoes",
            "paciente_nome",
            "paciente_cpf",
        ]

    def __init__(self, *args, **kwargs):
        unidades_qs = kwargs.pop("unidades_qs", None)
        profissionais_qs = kwargs.pop("profissionais_qs", None)
        super().__init__(*args, **kwargs)

        # Filtros de escopo
        if unidades_qs is not None and "unidade" in self.fields:
            self.fields["unidade"].queryset = unidades_qs

        if profissionais_qs is not None and "profissional" in self.fields:
            self.fields["profissional"].queryset = profissionais_qs

        # Aluno obrigatório (fase atual)
        if "aluno" in self.fields:
            self.fields["aluno"].queryset = Aluno.objects.all().order_by("nome")
            self.fields["aluno"].required = True

        # Compatibilidade: se aluno preenchido, paciente_* pode ficar vazio
        if "paciente_nome" in self.fields:
            self.fields["paciente_nome"].required = False
        if "paciente_cpf" in self.fields:
            self.fields["paciente_cpf"].required = False