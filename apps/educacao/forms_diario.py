from __future__ import annotations

from django import forms
from django.db.models import Q

from .forms_bncc import BNCCModelMultipleChoiceField
from .models_calendario import CalendarioEducacionalEvento
from .models_diario import Aula
from .models_notas import BNCCCodigo, ComponenteCurricular
from .models_periodos import PeriodoLetivo


def _bncc_context_from_turma(turma):
    if turma is None:
        return {
            "modalidades": [],
            "etapas": [],
            "anos": None,
            "hint": "Sem turma vinculada.",
        }

    modalidade = getattr(turma, "modalidade", "")
    etapa = getattr(turma, "etapa", "")

    if modalidade == "EDUCACAO_INFANTIL" or etapa in {"CRECHE", "PRE_ESCOLA"}:
        return {
            "modalidades": [BNCCCodigo.Modalidade.EDUCACAO_INFANTIL],
            "etapas": [BNCCCodigo.Etapa.EDUCACAO_INFANTIL],
            "anos": None,
            "hint": "Educação Infantil (BNCC EI).",
        }

    if etapa in {"FUNDAMENTAL_ANOS_INICIAIS", "EJA_FUNDAMENTAL"}:
        return {
            "modalidades": [BNCCCodigo.Modalidade.ENSINO_FUNDAMENTAL],
            "etapas": [BNCCCodigo.Etapa.FUNDAMENTAL_ANOS_INICIAIS],
            "anos": list(range(1, 6)),
            "hint": "Ensino Fundamental - Anos Iniciais (1º ao 5º).",
        }

    if etapa == "FUNDAMENTAL_ANOS_FINAIS":
        return {
            "modalidades": [BNCCCodigo.Modalidade.ENSINO_FUNDAMENTAL],
            "etapas": [BNCCCodigo.Etapa.FUNDAMENTAL_ANOS_FINAIS],
            "anos": list(range(6, 10)),
            "hint": "Ensino Fundamental - Anos Finais (6º ao 9º).",
        }

    if etapa in {"ENSINO_MEDIO", "EJA_MEDIO", "TECNICO_INTEGRADO", "TECNICO_CONCOMITANTE", "TECNICO_SUBSEQUENTE"}:
        return {
            "modalidades": [BNCCCodigo.Modalidade.ENSINO_MEDIO],
            "etapas": [BNCCCodigo.Etapa.ENSINO_MEDIO],
            "anos": None,
            "hint": "Ensino Médio (BNCC EM).",
        }

    if modalidade == "EJA":
        return {
            "modalidades": [BNCCCodigo.Modalidade.ENSINO_FUNDAMENTAL, BNCCCodigo.Modalidade.ENSINO_MEDIO],
            "etapas": [BNCCCodigo.Etapa.FUNDAMENTAL_ANOS_INICIAIS, BNCCCodigo.Etapa.FUNDAMENTAL_ANOS_FINAIS, BNCCCodigo.Etapa.ENSINO_MEDIO],
            "anos": None,
            "hint": "EJA (códigos BNCC do Fundamental e Médio).",
        }

    return {
        "modalidades": [BNCCCodigo.Modalidade.ENSINO_FUNDAMENTAL, BNCCCodigo.Modalidade.ENSINO_MEDIO],
        "etapas": [BNCCCodigo.Etapa.FUNDAMENTAL_ANOS_INICIAIS, BNCCCodigo.Etapa.FUNDAMENTAL_ANOS_FINAIS, BNCCCodigo.Etapa.ENSINO_MEDIO],
        "anos": None,
        "hint": "Modalidade ampla (códigos BNCC do Fundamental e Médio).",
    }


class AulaForm(forms.ModelForm):
    class Meta:
        model = Aula
        fields = [
            "data",
            "periodo",
            "componente",
            "bncc_codigos",
            "conteudo",
            "observacoes",
        ]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}),
            "bncc_codigos": forms.SelectMultiple(attrs={"size": 10}),
        }

    def __init__(self, *args, **kwargs):
        self.diario = kwargs.pop("diario", None)
        super().__init__(*args, **kwargs)

        self.fields["periodo"].required = False
        self.fields["componente"].required = False
        self.fields["bncc_codigos"].required = False

        self.fields["periodo"].queryset = PeriodoLetivo.objects.none()
        self.fields["componente"].queryset = ComponenteCurricular.objects.filter(ativo=True).order_by("nome")
        self.fields["bncc_codigos"] = BNCCModelMultipleChoiceField(
            queryset=BNCCCodigo.objects.filter(ativo=True).order_by("codigo"),
            required=False,
            widget=forms.SelectMultiple(attrs={"size": 10}),
            label="Códigos BNCC da aula",
            help_text="Pesquise e selecione os códigos BNCC que foram trabalhados nesta aula.",
        )

        self.bncc_hint = "Selecione a turma para filtrar os códigos BNCC."

        if not self.diario:
            return

        turma = self.diario.turma
        ano = getattr(turma, "ano_letivo", None)
        context = _bncc_context_from_turma(turma)
        self.bncc_hint = context["hint"]

        periodos_qs = PeriodoLetivo.objects.filter(ativo=True)
        if ano:
            periodos_qs = periodos_qs.filter(ano_letivo=ano)
        self.fields["periodo"].queryset = periodos_qs.order_by("numero")

        componentes_qs = self.fields["componente"].queryset
        if context["modalidades"]:
            componentes_qs = componentes_qs.filter(
                Q(modalidade_bncc="") | Q(modalidade_bncc__in=context["modalidades"])
            )
        if context["etapas"]:
            componentes_qs = componentes_qs.filter(
                Q(etapa_bncc="") | Q(etapa_bncc__in=context["etapas"])
            )
        self.fields["componente"].queryset = componentes_qs.order_by("nome")

        bncc_qs = self.fields["bncc_codigos"].queryset
        if context["modalidades"]:
            bncc_qs = bncc_qs.filter(modalidade__in=context["modalidades"])
        if context["etapas"]:
            bncc_qs = bncc_qs.filter(etapa__in=context["etapas"])
        if context["anos"]:
            bncc_qs = bncc_qs.filter(ano_inicial__in=context["anos"])

        componente_id = None
        if self.data.get("componente"):
            componente_id = self.data.get("componente")
        elif self.initial.get("componente"):
            componente_id = self.initial.get("componente")
        elif self.instance and self.instance.pk and self.instance.componente_id:
            componente_id = self.instance.componente_id

        if componente_id and str(componente_id).isdigit():
            componente = ComponenteCurricular.objects.filter(pk=int(componente_id)).first()
            if componente:
                has_vinculos = componente.bncc_codigos.filter(ativo=True).exists()
                if has_vinculos:
                    bncc_qs = bncc_qs.filter(pk__in=componente.bncc_codigos.values_list("pk", flat=True))
                elif componente.area_codigo_bncc:
                    bncc_qs = bncc_qs.filter(area_codigo=(componente.area_codigo_bncc or "").strip().upper())
                if componente.codigo_bncc_referencia:
                    bncc_qs = bncc_qs | BNCCCodigo.objects.filter(codigo=componente.codigo_bncc_referencia.strip().upper(), ativo=True)

        self.fields["bncc_codigos"].queryset = bncc_qs.distinct().order_by("codigo")

        data_ref = None
        if self.data.get("data"):
            try:
                data_ref = forms.DateField().clean(self.data.get("data"))
            except forms.ValidationError:
                data_ref = None
        elif self.instance and self.instance.pk and self.instance.data:
            data_ref = self.instance.data

        if data_ref and not self.data.get("periodo"):
            periodo_auto = periodos_qs.filter(inicio__lte=data_ref, fim__gte=data_ref).order_by("numero").first()
            if periodo_auto:
                self.fields["periodo"].initial = periodo_auto.pk

    def clean(self):
        cleaned = super().clean()
        if not self.diario:
            return cleaned

        turma = self.diario.turma
        data = cleaned.get("data")
        periodo = cleaned.get("periodo")
        codigos = cleaned.get("bncc_codigos")

        if data and getattr(turma, "ano_letivo", None):
            if data.year != int(turma.ano_letivo):
                self.add_error("data", f"A data da aula deve estar no ano letivo {turma.ano_letivo}.")

        periodos_qs = PeriodoLetivo.objects.filter(
            ano_letivo=getattr(turma, "ano_letivo", None),
            ativo=True,
        )
        if periodo and data:
            if not (periodo.inicio <= data <= periodo.fim):
                self.add_error("periodo", "A data da aula precisa estar dentro do período letivo selecionado.")
        elif data and not periodo:
            periodo_auto = periodos_qs.filter(inicio__lte=data, fim__gte=data).order_by("numero").first()
            if periodo_auto:
                cleaned["periodo"] = periodo_auto

        if data:
            eventos_qs = CalendarioEducacionalEvento.objects.filter(
                ativo=True,
                ano_letivo=getattr(turma, "ano_letivo", None),
                secretaria=getattr(getattr(turma, "unidade", None), "secretaria", None),
                data_inicio__lte=data,
                data_fim__gte=data,
            ).filter(
                Q(unidade__isnull=True) | Q(unidade=getattr(turma, "unidade", None))
            )
            if eventos_qs.filter(
                tipo__in=[
                    CalendarioEducacionalEvento.Tipo.FERIADO,
                    CalendarioEducacionalEvento.Tipo.RECESSO,
                ],
                dia_letivo=False,
            ).exists():
                self.add_error("data", "A data selecionada está marcada como não letiva no calendário educacional.")

        context = _bncc_context_from_turma(turma)
        modalidades_validas = set(context["modalidades"])
        etapas_validas = set(context["etapas"])
        if codigos:
            for codigo in codigos:
                if modalidades_validas and codigo.modalidade not in modalidades_validas:
                    self.add_error("bncc_codigos", f"Código {codigo.codigo} fora da modalidade da turma.")
                    break
                if etapas_validas and codigo.etapa not in etapas_validas:
                    self.add_error("bncc_codigos", f"Código {codigo.codigo} fora da etapa da turma.")
                    break

        return cleaned
