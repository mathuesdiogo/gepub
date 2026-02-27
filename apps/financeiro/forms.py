from __future__ import annotations

import os

from django import forms
from django.db.models import F

from .models import (
    DespEmpenho,
    DespLiquidacao,
    DespPagamento,
    DespPagamentoResto,
    DespRestosPagar,
    FinanceiroContaBancaria,
    FinanceiroExercicio,
    FinanceiroUnidadeGestora,
    OrcCreditoAdicional,
    OrcDotacao,
    OrcFonteRecurso,
    RecArrecadacao,
    TesExtratoImportacao,
)


class FinanceiroExercicioForm(forms.ModelForm):
    class Meta:
        model = FinanceiroExercicio
        fields = [
            "ano",
            "status",
            "inicio_em",
            "fim_em",
            "fechamento_mensal_ate",
            "observacoes",
        ]


class FinanceiroUnidadeGestoraForm(forms.ModelForm):
    class Meta:
        model = FinanceiroUnidadeGestora
        fields = ["codigo", "nome", "secretaria", "unidade", "ativo"]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["secretaria"].queryset = self.fields["secretaria"].queryset.filter(municipio=municipio)
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(secretaria__municipio=municipio)


class FinanceiroContaBancariaForm(forms.ModelForm):
    class Meta:
        model = FinanceiroContaBancaria
        fields = [
            "unidade_gestora",
            "banco_codigo",
            "banco_nome",
            "agencia",
            "conta",
            "tipo_conta",
            "saldo_atual",
            "ativo",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["unidade_gestora"].queryset = self.fields["unidade_gestora"].queryset.filter(municipio=municipio)


class OrcFonteRecursoForm(forms.ModelForm):
    class Meta:
        model = OrcFonteRecurso
        fields = ["codigo", "nome", "ativo"]


class OrcDotacaoForm(forms.ModelForm):
    class Meta:
        model = OrcDotacao
        fields = [
            "exercicio",
            "unidade_gestora",
            "secretaria",
            "programa_codigo",
            "programa_nome",
            "acao_codigo",
            "acao_nome",
            "elemento_despesa",
            "fonte",
            "valor_inicial",
            "valor_atualizado",
            "ativo",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["exercicio"].queryset = self.fields["exercicio"].queryset.filter(municipio=municipio)
            self.fields["unidade_gestora"].queryset = self.fields["unidade_gestora"].queryset.filter(municipio=municipio)
            self.fields["secretaria"].queryset = self.fields["secretaria"].queryset.filter(municipio=municipio)
            self.fields["fonte"].queryset = self.fields["fonte"].queryset.filter(municipio=municipio)


class OrcCreditoAdicionalForm(forms.ModelForm):
    class Meta:
        model = OrcCreditoAdicional
        fields = [
            "exercicio",
            "dotacao",
            "tipo",
            "numero_ato",
            "data_ato",
            "valor",
            "origem_recurso",
            "descricao",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["exercicio"].queryset = self.fields["exercicio"].queryset.filter(municipio=municipio)
            self.fields["dotacao"].queryset = self.fields["dotacao"].queryset.filter(municipio=municipio, ativo=True)

    def clean(self):
        cleaned = super().clean()
        exercicio = cleaned.get("exercicio")
        dotacao = cleaned.get("dotacao")
        valor = cleaned.get("valor")

        if exercicio and dotacao and dotacao.exercicio_id != exercicio.id:
            self.add_error("dotacao", "A dotação precisa pertencer ao exercício selecionado.")
        if valor is not None and valor <= 0:
            self.add_error("valor", "Informe um valor de crédito maior que zero.")

        return cleaned


class DespEmpenhoForm(forms.ModelForm):
    class Meta:
        model = DespEmpenho
        fields = [
            "exercicio",
            "unidade_gestora",
            "dotacao",
            "numero",
            "data_empenho",
            "fornecedor_nome",
            "fornecedor_documento",
            "objeto",
            "tipo",
            "valor_empenhado",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["exercicio"].queryset = self.fields["exercicio"].queryset.filter(municipio=municipio)
            self.fields["unidade_gestora"].queryset = self.fields["unidade_gestora"].queryset.filter(municipio=municipio)
            self.fields["dotacao"].queryset = self.fields["dotacao"].queryset.filter(municipio=municipio, ativo=True)


class DespLiquidacaoForm(forms.ModelForm):
    class Meta:
        model = DespLiquidacao
        fields = ["numero", "data_liquidacao", "documento_fiscal", "observacao", "valor_liquidado"]


class DespPagamentoForm(forms.ModelForm):
    class Meta:
        model = DespPagamento
        fields = ["conta_bancaria", "ordem_pagamento", "data_pagamento", "valor_pago", "status"]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["conta_bancaria"].queryset = self.fields["conta_bancaria"].queryset.filter(municipio=municipio, ativo=True)


class DespRestosPagarForm(forms.ModelForm):
    class Meta:
        model = DespRestosPagar
        fields = [
            "exercicio_inscricao",
            "empenho",
            "tipo",
            "numero_inscricao",
            "data_inscricao",
            "valor_inscrito",
            "observacao",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["exercicio_inscricao"].queryset = self.fields["exercicio_inscricao"].queryset.filter(municipio=municipio)
            self.fields["empenho"].queryset = self.fields["empenho"].queryset.filter(
                municipio=municipio,
                valor_liquidado__gt=F("valor_pago"),
            )

    def clean(self):
        cleaned = super().clean()
        empenho = cleaned.get("empenho")
        valor_inscrito = cleaned.get("valor_inscrito")

        if empenho and valor_inscrito is not None:
            if valor_inscrito <= 0:
                self.add_error("valor_inscrito", "Informe um valor inscrito maior que zero.")
            elif valor_inscrito > empenho.saldo_a_pagar:
                self.add_error("valor_inscrito", "Valor inscrito excede o saldo a pagar do empenho.")

        return cleaned


class DespPagamentoRestoForm(forms.ModelForm):
    class Meta:
        model = DespPagamentoResto
        fields = ["conta_bancaria", "ordem_pagamento", "data_pagamento", "valor", "status"]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["conta_bancaria"].queryset = self.fields["conta_bancaria"].queryset.filter(municipio=municipio, ativo=True)

    def clean_valor(self):
        valor = self.cleaned_data.get("valor")
        if valor is not None and valor <= 0:
            raise forms.ValidationError("Informe um valor de pagamento maior que zero.")
        return valor


class TesExtratoImportacaoUploadForm(forms.Form):
    exercicio = forms.ModelChoiceField(queryset=FinanceiroExercicio.objects.none(), label="Exercício")
    conta_bancaria = forms.ModelChoiceField(queryset=FinanceiroContaBancaria.objects.none(), label="Conta bancária")
    formato = forms.ChoiceField(choices=TesExtratoImportacao.Formato.choices, label="Formato")
    arquivo = forms.FileField(label="Arquivo do extrato")
    observacao = forms.CharField(label="Observação", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["exercicio"].queryset = FinanceiroExercicio.objects.filter(municipio=municipio).order_by("-ano")
            self.fields["conta_bancaria"].queryset = FinanceiroContaBancaria.objects.filter(municipio=municipio, ativo=True).order_by(
                "banco_nome",
                "agencia",
                "conta",
            )

    def clean(self):
        cleaned = super().clean()
        formato = cleaned.get("formato")
        arquivo = cleaned.get("arquivo")
        if not arquivo or not formato:
            return cleaned

        ext = os.path.splitext(arquivo.name or "")[1].lower()
        if formato == TesExtratoImportacao.Formato.CSV and ext and ext not in {".csv", ".txt"}:
            self.add_error("arquivo", "Para formato CSV, envie arquivo .csv ou .txt.")
        if formato == TesExtratoImportacao.Formato.OFX and ext and ext not in {".ofx"}:
            self.add_error("arquivo", "Para formato OFX, envie arquivo .ofx.")
        return cleaned


class RecConciliacaoAjusteForm(forms.Form):
    observacao = forms.CharField(label="Observação", required=False, max_length=200)


class RecArrecadacaoForm(forms.ModelForm):
    class Meta:
        model = RecArrecadacao
        fields = [
            "exercicio",
            "unidade_gestora",
            "conta_bancaria",
            "data_arrecadacao",
            "rubrica_codigo",
            "rubrica_nome",
            "valor",
            "documento",
            "origem",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["exercicio"].queryset = self.fields["exercicio"].queryset.filter(municipio=municipio)
            self.fields["unidade_gestora"].queryset = self.fields["unidade_gestora"].queryset.filter(municipio=municipio)
            self.fields["conta_bancaria"].queryset = self.fields["conta_bancaria"].queryset.filter(municipio=municipio, ativo=True)
