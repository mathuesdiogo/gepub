from __future__ import annotations

from datetime import datetime

from django import forms
from django.contrib.auth import get_user_model

from apps.accounts.models import Profile
from apps.org.services.cadastros_base import aplicar_sugestoes_em_campo, mapear_sugestoes_por_categoria

from .models import PontoCadastro, PontoFechamentoCompetencia, PontoOcorrencia, PontoVinculoEscala


User = get_user_model()


class PontoCadastroForm(forms.ModelForm):
    class Meta:
        model = PontoCadastro
        fields = [
            "secretaria",
            "unidade",
            "setor",
            "codigo",
            "nome",
            "tipo_turno",
            "hora_entrada",
            "hora_saida",
            "carga_horaria_semanal",
            "tolerancia_entrada_min",
            "dias_semana",
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
                categorias=["TURNO"],
            )
            aplicar_sugestoes_em_campo(self, "tipo_turno", sugestoes.get("TURNO"))

    def clean(self):
        cleaned = super().clean()
        hora_entrada = cleaned.get("hora_entrada")
        hora_saida = cleaned.get("hora_saida")
        if hora_entrada and hora_saida and hora_saida <= hora_entrada:
            self.add_error("hora_saida", "A hora de saída deve ser maior que a hora de entrada.")
        return cleaned


class PontoVinculoEscalaForm(forms.ModelForm):
    class Meta:
        model = PontoVinculoEscala
        fields = [
            "escala",
            "servidor",
            "unidade",
            "setor",
            "data_inicio",
            "data_fim",
            "ativo",
            "observacao",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.municipio = municipio
        if municipio is not None:
            self.fields["escala"].queryset = PontoCadastro.objects.filter(municipio=municipio).order_by("nome")
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(secretaria__municipio=municipio)
            self.fields["setor"].queryset = self.fields["setor"].queryset.filter(unidade__secretaria__municipio=municipio)
            self.fields["servidor"].queryset = (
                User.objects.filter(
                    profile__municipio=municipio,
                    profile__ativo=True,
                )
                .exclude(profile__role=Profile.Role.ALUNO)
                .order_by("first_name", "username")
            )
        self.fields["servidor"].label_from_instance = lambda obj: (obj.get_full_name() or obj.username).strip()

    def clean(self):
        cleaned = super().clean()
        unidade = cleaned.get("unidade")
        setor = cleaned.get("setor")
        escala = cleaned.get("escala")
        data_inicio = cleaned.get("data_inicio")
        data_fim = cleaned.get("data_fim")

        if setor and unidade and setor.unidade_id != unidade.id:
            self.add_error("setor", "O setor informado não pertence à unidade selecionada.")

        if escala and self.municipio and escala.municipio_id != self.municipio.id:
            self.add_error("escala", "A escala selecionada não pertence ao município.")

        if data_inicio and data_fim and data_fim < data_inicio:
            self.add_error("data_fim", "A data final não pode ser menor que a data inicial.")

        return cleaned


class PontoOcorrenciaForm(forms.ModelForm):
    class Meta:
        model = PontoOcorrencia
        fields = [
            "servidor",
            "vinculo",
            "data_ocorrencia",
            "tipo",
            "minutos",
            "descricao",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.municipio = municipio
        if municipio is not None:
            self.fields["vinculo"].queryset = (
                PontoVinculoEscala.objects.filter(municipio=municipio).select_related("servidor", "escala")
            )
            self.fields["servidor"].queryset = (
                User.objects.filter(
                    profile__municipio=municipio,
                    profile__ativo=True,
                )
                .exclude(profile__role=Profile.Role.ALUNO)
                .order_by("first_name", "username")
            )
        self.fields["servidor"].label_from_instance = lambda obj: (obj.get_full_name() or obj.username).strip()
        self.fields["vinculo"].required = False

    def clean(self):
        cleaned = super().clean()
        vinculo = cleaned.get("vinculo")
        servidor = cleaned.get("servidor")
        minutos = cleaned.get("minutos") or 0

        if minutos < 0:
            self.add_error("minutos", "Minutos não pode ser negativo.")

        if vinculo and servidor and vinculo.servidor_id != servidor.id:
            self.add_error("vinculo", "O vínculo selecionado pertence a outro servidor.")

        if vinculo and self.municipio and vinculo.municipio_id != self.municipio.id:
            self.add_error("vinculo", "O vínculo selecionado não pertence ao município.")

        return cleaned


class PontoFechamentoCompetenciaForm(forms.ModelForm):
    class Meta:
        model = PontoFechamentoCompetencia
        fields = ["competencia", "observacao"]

    def clean_competencia(self):
        competencia = (self.cleaned_data.get("competencia") or "").strip()
        try:
            datetime.strptime(competencia, "%Y-%m")
        except ValueError as exc:
            raise forms.ValidationError("Competência inválida. Use o formato YYYY-MM.") from exc
        return competencia
