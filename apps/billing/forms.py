from __future__ import annotations

from django import forms

from .models import (
    AddonCatalogo,
    AssinaturaMunicipio,
    AssinaturaQuotaExtra,
    PlanoComercialConfig,
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
        qs = PlanoMunicipal.objects.filter(
            ativo=True,
            codigo__in=[
                PlanoMunicipal.Codigo.STARTER,
                PlanoMunicipal.Codigo.MUNICIPAL,
                PlanoMunicipal.Codigo.GESTAO_TOTAL,
                PlanoMunicipal.Codigo.CONSORCIO,
            ],
        )
        if self.instance and getattr(self.instance, "plano_id", None):
            qs = PlanoMunicipal.objects.filter(pk=self.instance.plano_id) | qs
        self.fields["plano"].queryset = qs.order_by("preco_base_mensal")
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

        self.fields["tipo"].choices = [
            (value, label)
            for value, label in self.fields["tipo"].choices
            if value != SolicitacaoUpgrade.Tipo.SECRETARIAS
        ]
        self.fields["addon"].queryset = AddonCatalogo.objects.filter(ativo=True).order_by("nome")
        self.fields["plano_destino"].queryset = PlanoMunicipal.objects.filter(
            ativo=True,
            codigo__in=[
                PlanoMunicipal.Codigo.STARTER,
                PlanoMunicipal.Codigo.MUNICIPAL,
                PlanoMunicipal.Codigo.GESTAO_TOTAL,
                PlanoMunicipal.Codigo.CONSORCIO,
            ],
        ).order_by("preco_base_mensal")
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


def _normalize_text_lines(value: str) -> list[str]:
    lines: list[str] = []
    for raw in (value or "").splitlines():
        item = (raw or "").strip().lstrip("-").strip()
        if item:
            lines.append(item)
    return lines


class PlanoMunicipalAdminForm(forms.ModelForm):
    class Meta:
        model = PlanoMunicipal
        fields = [
            "codigo",
            "nome",
            "descricao",
            "ativo",
            "preco_base_mensal",
            "limite_usuarios",
            "limite_alunos",
            "limite_atendimentos_ano",
            "valor_usuario_extra",
            "valor_aluno_extra",
            "valor_atendimento_extra",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        allowed = {
            PlanoMunicipal.Codigo.STARTER,
            PlanoMunicipal.Codigo.MUNICIPAL,
            PlanoMunicipal.Codigo.GESTAO_TOTAL,
            PlanoMunicipal.Codigo.CONSORCIO,
        }
        current = None
        if self.instance and getattr(self.instance, "pk", None):
            current = self.instance.codigo
        self.fields["codigo"].choices = [
            (value, label)
            for value, label in self.fields["codigo"].choices
            if value in allowed or (current and value == current)
        ]


class PlanoComercialConfigForm(forms.ModelForm):
    beneficios_text = forms.CharField(
        required=False,
        label="Benefícios (1 por linha)",
        widget=forms.Textarea(attrs={"rows": 5}),
    )
    especiais_text = forms.CharField(
        required=False,
        label="Acessos especiais (1 por linha)",
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    limitacoes_text = forms.CharField(
        required=False,
        label="Limitações (1 por linha)",
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    dependencias_text = forms.CharField(
        required=False,
        label="Dependências/recomendações (1 por linha)",
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    class Meta:
        model = PlanoComercialConfig
        fields = [
            "nome_comercial",
            "categoria",
            "descricao_comercial",
            "link_documento_contratacao",
            "link_documento_servicos",
        ]
        widgets = {
            "descricao_comercial": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = self.instance
        if inst and getattr(inst, "pk", None):
            self.fields["beneficios_text"].initial = "\n".join(inst.beneficios or [])
            self.fields["especiais_text"].initial = "\n".join(inst.especiais or [])
            self.fields["limitacoes_text"].initial = "\n".join(inst.limitacoes or [])
            self.fields["dependencias_text"].initial = "\n".join(inst.dependencias or [])

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.beneficios = _normalize_text_lines(self.cleaned_data.get("beneficios_text", ""))
        instance.especiais = _normalize_text_lines(self.cleaned_data.get("especiais_text", ""))
        instance.limitacoes = _normalize_text_lines(self.cleaned_data.get("limitacoes_text", ""))
        instance.dependencias = _normalize_text_lines(self.cleaned_data.get("dependencias_text", ""))
        if commit:
            instance.save()
        return instance
