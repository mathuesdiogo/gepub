from __future__ import annotations

from django import forms

from apps.accounts.models import Profile
from apps.org.models import Secretaria, Setor, Unidade
from apps.org.services.cadastros_base import aplicar_sugestoes_em_campo, mapear_sugestoes_por_categoria

from .models import RhCadastro, RhDocumento, RhMovimentacao


class RhCadastroForm(forms.ModelForm):
    class Meta:
        model = RhCadastro
        fields = [
            "servidor",
            "secretaria",
            "unidade",
            "setor",
            "codigo",
            "matricula",
            "nome",
            "cargo",
            "funcao",
            "regime",
            "data_admissao",
            "situacao_funcional",
            "salario_base",
            "data_desligamento",
            "status",
            "observacao",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.municipio = municipio
        if municipio is not None:
            self.fields["secretaria"].queryset = self.fields["secretaria"].queryset.filter(municipio=municipio)
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(secretaria__municipio=municipio)
            self.fields["setor"].queryset = self.fields["setor"].queryset.filter(unidade__secretaria__municipio=municipio)
            self.fields["servidor"].queryset = (
                self.fields["servidor"]
                .queryset.filter(profile__municipio=municipio, profile__ativo=True)
                .exclude(profile__role=Profile.Role.ALUNO)
            )
            sugestoes = mapear_sugestoes_por_categoria(
                municipio_id=municipio.id,
                categorias=["CARGO", "CARGO_FUNCAO"],
            )
            aplicar_sugestoes_em_campo(self, "cargo", sugestoes.get("CARGO") or sugestoes.get("CARGO_FUNCAO"))
            aplicar_sugestoes_em_campo(self, "funcao", sugestoes.get("CARGO_FUNCAO") or sugestoes.get("CARGO"))
        self.fields["servidor"].required = False

    def clean(self):
        cleaned = super().clean()
        unidade = cleaned.get("unidade")
        setor = cleaned.get("setor")
        desligamento = cleaned.get("data_desligamento")
        admissao = cleaned.get("data_admissao")
        situacao = cleaned.get("situacao_funcional")
        matricula = (cleaned.get("matricula") or "").strip()

        if setor and unidade and setor.unidade_id != unidade.id:
            self.add_error("setor", "O setor informado não pertence à unidade selecionada.")
        if admissao and desligamento and desligamento < admissao:
            self.add_error("data_desligamento", "Data de desligamento não pode ser menor que a data de admissão.")
        if situacao == RhCadastro.SituacaoFuncional.DESLIGADO and not desligamento:
            self.add_error("data_desligamento", "Informe a data de desligamento para situação desligado.")
        if not matricula:
            cleaned["matricula"] = (cleaned.get("codigo") or "").strip()
        return cleaned


class RhMovimentacaoForm(forms.ModelForm):
    class Meta:
        model = RhMovimentacao
        fields = [
            "servidor",
            "tipo",
            "data_inicio",
            "data_fim",
            "secretaria_destino",
            "unidade_destino",
            "setor_destino",
            "observacao",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.municipio = municipio
        if municipio is not None:
            self.fields["servidor"].queryset = RhCadastro.objects.filter(municipio=municipio, status=RhCadastro.Status.ATIVO)
            self.fields["secretaria_destino"].queryset = Secretaria.objects.filter(municipio=municipio, ativo=True)
            self.fields["unidade_destino"].queryset = Unidade.objects.filter(secretaria__municipio=municipio, ativo=True)
            self.fields["setor_destino"].queryset = Setor.objects.filter(unidade__secretaria__municipio=municipio, ativo=True)

    def clean(self):
        cleaned = super().clean()
        inicio = cleaned.get("data_inicio")
        fim = cleaned.get("data_fim")
        unidade = cleaned.get("unidade_destino")
        setor = cleaned.get("setor_destino")
        if inicio and fim and fim < inicio:
            self.add_error("data_fim", "Data final não pode ser menor que a data inicial.")
        if setor and unidade and setor.unidade_id != unidade.id:
            self.add_error("setor_destino", "O setor destino deve pertencer à unidade destino.")
        return cleaned


class RhDocumentoForm(forms.ModelForm):
    class Meta:
        model = RhDocumento
        fields = ["servidor", "tipo", "numero", "data_documento", "descricao", "arquivo"]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["servidor"].queryset = RhCadastro.objects.filter(municipio=municipio).order_by("nome")
            sugestoes = mapear_sugestoes_por_categoria(
                municipio_id=municipio.id,
                categorias=["DOCUMENTO_TIPO"],
            )
            aplicar_sugestoes_em_campo(self, "tipo", sugestoes.get("DOCUMENTO_TIPO"))
