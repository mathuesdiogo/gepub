from __future__ import annotations

from django import forms
from django.db.models import Q
from django.utils import timezone

from apps.core.rbac import scope_filter_unidades
from apps.org.models import Secretaria, Unidade

from .models_programas import (
    ProgramaComplementar,
    ProgramaComplementarFrequencia,
    ProgramaComplementarHorario,
    ProgramaComplementarOferta,
    ProgramaComplementarParticipacao,
)
from .services_programas import ProgramasComplementaresService


def _unidades_educacao_scope(user):
    return scope_filter_unidades(
        user,
        Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO),
    )


class ProgramaComplementarForm(forms.ModelForm):
    class Meta:
        model = ProgramaComplementar
        fields = [
            "nome",
            "tipo",
            "slug",
            "descricao",
            "objetivo",
            "publico_alvo",
            "faixa_etaria_min",
            "faixa_etaria_max",
            "exige_vinculo_escolar_ativo",
            "permite_multiplas_participacoes",
            "status",
            "secretaria_responsavel",
            "unidade_gestora",
            "observacoes",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            unidades = _unidades_educacao_scope(user)
            secretarias_ids = unidades.values_list("secretaria_id", flat=True).distinct()
            self.fields["unidade_gestora"].queryset = unidades
            self.fields["secretaria_responsavel"].queryset = Secretaria.objects.filter(id__in=secretarias_ids)


class ProgramaComplementarOfertaForm(forms.ModelForm):
    class Meta:
        model = ProgramaComplementarOferta
        fields = [
            "programa",
            "unidade",
            "ano_letivo",
            "codigo",
            "nome",
            "turno",
            "capacidade_maxima",
            "idade_minima",
            "idade_maxima",
            "data_inicio",
            "data_fim",
            "responsavel",
            "status",
            "exige_vinculo_escolar_ativo",
            "permite_sobreposicao_horario",
            "observacoes",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            unidades = _unidades_educacao_scope(user)
            secretarias_ids = unidades.values_list("secretaria_id", flat=True).distinct()
            self.fields["unidade"].queryset = unidades
            self.fields["programa"].queryset = ProgramaComplementar.objects.filter(
                status=ProgramaComplementar.Status.ATIVO
            ).filter(
                Q(secretaria_responsavel_id__in=secretarias_ids)
                | Q(unidade_gestora_id__in=unidades.values_list("id", flat=True))
                | Q(secretaria_responsavel__isnull=True, unidade_gestora__isnull=True)
            )


class ProgramaComplementarHorarioForm(forms.ModelForm):
    class Meta:
        model = ProgramaComplementarHorario
        fields = [
            "oferta",
            "dia_semana",
            "hora_inicio",
            "hora_fim",
            "frequencia_tipo",
            "turno",
            "ativo",
            "observacoes",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            unidades = _unidades_educacao_scope(user)
            self.fields["oferta"].queryset = ProgramaComplementarOferta.objects.select_related(
                "programa", "unidade"
            ).filter(unidade__in=unidades)


class ProgramaComplementarParticipacaoCreateForm(forms.Form):
    oferta = forms.ModelChoiceField(queryset=ProgramaComplementarOferta.objects.none(), label="Oferta")
    identificador_aluno = forms.CharField(
        max_length=120,
        label="Aluno (matrícula / código de acesso / nome)",
        help_text="Você pode buscar por matrícula institucional, código de acesso ou nome.",
    )
    escola_origem = forms.ModelChoiceField(
        queryset=Unidade.objects.none(),
        required=False,
        label="Escola de origem",
    )
    data_ingresso = forms.DateField(initial=timezone.localdate, required=False)
    status = forms.ChoiceField(
        choices=[
            (ProgramaComplementarParticipacao.Status.ATIVO, "Ativo"),
            (ProgramaComplementarParticipacao.Status.PRE_INSCRITO, "Pré-inscrito"),
            (ProgramaComplementarParticipacao.Status.AGUARDANDO_VAGA, "Aguardando vaga"),
        ],
        initial=ProgramaComplementarParticipacao.Status.ATIVO,
    )
    observacoes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    allow_override_conflict = forms.BooleanField(required=False, label="Permitir exceção de conflito")
    override_justificativa = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Justificativa da exceção",
    )

    def __init__(self, *args, user=None, allow_override=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.allow_override = bool(allow_override)
        self.aluno = None
        unidades = _unidades_educacao_scope(user) if user else Unidade.objects.none()
        self.fields["escola_origem"].queryset = unidades
        self.fields["oferta"].queryset = ProgramaComplementarOferta.objects.select_related(
            "programa", "unidade"
        ).filter(
            unidade__in=unidades,
            status=ProgramaComplementarOferta.Status.ATIVA,
            programa__status=ProgramaComplementar.Status.ATIVO,
        )
        if not self.allow_override:
            self.fields.pop("allow_override_conflict", None)
            self.fields.pop("override_justificativa", None)

    def clean(self):
        cleaned = super().clean()
        token = (cleaned.get("identificador_aluno") or "").strip()
        if not token:
            self.add_error("identificador_aluno", "Informe um identificador de aluno.")
            return cleaned

        aluno = ProgramasComplementaresService.find_student_by_identifier(token)
        if aluno is None:
            self.add_error("identificador_aluno", "Aluno não encontrado para o identificador informado.")
            return cleaned
        self.aluno = aluno

        offer = cleaned.get("oferta")
        escola_origem = cleaned.get("escola_origem")
        if offer and escola_origem and getattr(escola_origem, "tipo", None) != Unidade.Tipo.EDUCACAO:
            self.add_error("escola_origem", "Selecione uma escola/unidade de Educação.")
        if (
            self.allow_override
            and cleaned.get("allow_override_conflict")
            and not (cleaned.get("override_justificativa") or "").strip()
        ):
            self.add_error("override_justificativa", "Informe justificativa ao permitir exceção de conflito.")
        return cleaned


class ProgramaComplementarFrequenciaForm(forms.Form):
    data_aula = forms.DateField(initial=timezone.localdate)
    status_presenca = forms.ChoiceField(choices=ProgramaComplementarFrequencia.StatusPresenca.choices)
    justificativa = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    observacoes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
