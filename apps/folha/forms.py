from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from apps.accounts.models import Profile

from .models import FolhaCadastro, FolhaCompetencia, FolhaLancamento


User = get_user_model()


class FolhaCadastroForm(forms.ModelForm):
    class Meta:
        model = FolhaCadastro
        fields = [
            "secretaria",
            "unidade",
            "setor",
            "codigo",
            "nome",
            "tipo_evento",
            "natureza",
            "valor_referencia",
            "formula_calculo",
            "status",
            "observacao",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["secretaria"].queryset = self.fields["secretaria"].queryset.filter(municipio=municipio)
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(secretaria__municipio=municipio)
            self.fields["setor"].queryset = self.fields["setor"].queryset.filter(unidade__secretaria__municipio=municipio)


class FolhaCompetenciaForm(forms.ModelForm):
    class Meta:
        model = FolhaCompetencia
        fields = ["competencia"]

    def clean_competencia(self):
        comp = (self.cleaned_data.get("competencia") or "").strip()
        try:
            datetime.strptime(comp, "%Y-%m")
        except ValueError as exc:
            raise forms.ValidationError("Competência inválida. Use o formato YYYY-MM.") from exc
        return comp


class FolhaLancamentoForm(forms.ModelForm):
    class Meta:
        model = FolhaLancamento
        fields = ["competencia", "servidor", "evento", "quantidade", "valor_unitario", "observacao"]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.municipio = municipio
        if municipio is not None:
            self.fields["competencia"].queryset = FolhaCompetencia.objects.filter(municipio=municipio).exclude(
                status=FolhaCompetencia.Status.FECHADA
            )
            self.fields["evento"].queryset = FolhaCadastro.objects.filter(municipio=municipio, status=FolhaCadastro.Status.ATIVO)
            self.fields["servidor"].queryset = (
                User.objects.filter(profile__municipio=municipio, profile__ativo=True)
                .exclude(profile__role=Profile.Role.ALUNO)
                .order_by("first_name", "username")
            )
            self.fields["servidor"].label_from_instance = lambda obj: (obj.get_full_name() or obj.username).strip()

    def clean(self):
        cleaned = super().clean()
        comp = cleaned.get("competencia")
        evento = cleaned.get("evento")
        valor_unitario = cleaned.get("valor_unitario")
        quantidade = cleaned.get("quantidade")

        if comp and self.municipio and comp.municipio_id != self.municipio.id:
            self.add_error("competencia", "A competência selecionada não pertence ao município.")
        if evento and self.municipio and evento.municipio_id != self.municipio.id:
            self.add_error("evento", "A rubrica selecionada não pertence ao município.")
        if comp and comp.status == FolhaCompetencia.Status.FECHADA:
            self.add_error("competencia", "Não é permitido lançar em competência fechada.")

        if evento and (valor_unitario is None or Decimal(valor_unitario) == Decimal("0")):
            cleaned["valor_unitario"] = evento.valor_referencia
        if quantidade is not None and Decimal(quantidade) <= Decimal("0"):
            self.add_error("quantidade", "Quantidade deve ser maior que zero.")
        return cleaned
