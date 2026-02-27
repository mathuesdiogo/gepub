from __future__ import annotations

from django import forms

from .models import (
    AddonCatalogo,
    AssinaturaMunicipio,
    AssinaturaQuotaExtra,
    PlanoMunicipal,
    SolicitacaoUpgrade,
)
from .services import calcular_valor_upgrade


class OnboardingPlanoForm(forms.ModelForm):
    class Meta:
        model = AssinaturaMunicipio
        fields = [
            "plano",
            "contrato_meses",
            "indice_reajuste",
            "desconto_percentual",
            "observacoes",
        ]
        widgets = {
            "observacoes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Observações comerciais/contratuais (opcional)",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plano"].queryset = PlanoMunicipal.objects.filter(ativo=True).order_by("preco_base_mensal")
        self.fields["contrato_meses"].initial = self.initial.get("contrato_meses") or 12
        self.fields["indice_reajuste"].initial = self.initial.get("indice_reajuste") or AssinaturaMunicipio.IndiceReajuste.INPC


class SolicitacaoUpgradeForm(forms.ModelForm):
    class Meta:
        model = SolicitacaoUpgrade
        fields = ["tipo", "quantidade", "addon", "plano_destino", "observacao"]
        widgets = {
            "observacao": forms.Textarea(attrs={"rows": 3, "placeholder": "Justificativa do pedido (opcional)"}),
        }

    def __init__(self, *args, assinatura: AssinaturaMunicipio | None = None, **kwargs):
        self.assinatura = assinatura
        self.valor_calculado = None
        super().__init__(*args, **kwargs)

        self.fields["addon"].queryset = AddonCatalogo.objects.filter(ativo=True).order_by("nome")
        self.fields["plano_destino"].queryset = PlanoMunicipal.objects.filter(ativo=True).order_by("preco_base_mensal")
        self.fields["quantidade"].initial = 1

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo")
        addon = cleaned.get("addon")
        plano_destino = cleaned.get("plano_destino")
        quantidade = int(cleaned.get("quantidade") or 1)

        if tipo == SolicitacaoUpgrade.Tipo.ADDON and not addon:
            self.add_error("addon", "Selecione um addon para este tipo de solicitação.")

        if tipo == SolicitacaoUpgrade.Tipo.TROCA_PLANO and not plano_destino:
            self.add_error("plano_destino", "Selecione o plano de destino.")

        if tipo != SolicitacaoUpgrade.Tipo.ADDON:
            cleaned["addon"] = None

        if tipo != SolicitacaoUpgrade.Tipo.TROCA_PLANO:
            cleaned["plano_destino"] = None

        if self.assinatura and tipo:
            self.valor_calculado = calcular_valor_upgrade(
                self.assinatura,
                tipo=tipo,
                quantidade=quantidade,
                addon=addon,
                plano_destino=plano_destino,
            )

        return cleaned


class SimuladorPlanoForm(forms.Form):
    populacao = forms.IntegerField(required=False, min_value=0, label="População (opcional)")
    numero_secretarias = forms.IntegerField(min_value=0, initial=4, label="Secretarias desejadas")
    numero_usuarios = forms.IntegerField(min_value=0, initial=60, label="Usuários previstos")
    numero_alunos = forms.IntegerField(min_value=0, initial=2000, label="Alunos previstos")
    atendimentos_estimados_ano = forms.IntegerField(min_value=0, initial=10000, label="Atendimentos clínicos/ano")


class AssinaturaAdminForm(forms.ModelForm):
    class Meta:
        model = AssinaturaMunicipio
        fields = [
            "plano",
            "status",
            "inicio_vigencia",
            "fim_vigencia",
            "preco_base_congelado",
            "indice_reajuste",
            "desconto_percentual",
            "contrato_meses",
            "observacoes",
        ]
        widgets = {
            "inicio_vigencia": forms.DateInput(attrs={"type": "date"}),
            "fim_vigencia": forms.DateInput(attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }


class BonusQuotaForm(forms.Form):
    tipo = forms.ChoiceField(choices=AssinaturaQuotaExtra.Tipo.choices, label="Tipo de quota")
    quantidade = forms.IntegerField(min_value=1, initial=100)
    validade_dias = forms.IntegerField(required=False, min_value=1, max_value=3650, label="Validade (dias, opcional)")
    descricao = forms.CharField(required=False, max_length=180)


class FiltroAssinaturaForm(forms.Form):
    q = forms.CharField(required=False, label="Buscar")
    status = forms.ChoiceField(
        required=False,
        choices=[("", "Todos os status")] + list(AssinaturaMunicipio.Status.choices),
    )
