from __future__ import annotations

from django import forms
from django.utils import timezone

from apps.core.rbac import is_admin, scope_filter_secretarias, scope_filter_unidades
from apps.org.models import Secretaria, Unidade

from .models_calendario import CalendarioEducacionalEvento


class CalendarioEducacionalEventoForm(forms.ModelForm):
    class Meta:
        model = CalendarioEducacionalEvento
        fields = [
            "ano_letivo",
            "secretaria",
            "unidade",
            "titulo",
            "descricao",
            "tipo",
            "data_inicio",
            "data_fim",
            "dia_letivo",
            "ativo",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 3}),
            "data_inicio": forms.DateInput(attrs={"type": "date"}),
            "data_fim": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["ano_letivo"].initial = self.instance.ano_letivo if self.instance.pk else timezone.localdate().year
        self.fields["unidade"].required = False
        self.fields["data_fim"].required = False

        secretarias_qs = Secretaria.objects.none()
        unidades_qs = Unidade.objects.none()

        if user is not None:
            if is_admin(user):
                secretarias_qs = Secretaria.objects.select_related("municipio").all().order_by("nome")
                unidades_qs = Unidade.objects.select_related("secretaria").all().order_by("nome")
            else:
                secretarias_qs = scope_filter_secretarias(user, Secretaria.objects.select_related("municipio").all()).order_by("nome")
                unidades_qs = scope_filter_unidades(user, Unidade.objects.select_related("secretaria").all()).order_by("nome")

        self.fields["secretaria"].queryset = secretarias_qs
        self.fields["unidade"].queryset = unidades_qs

        secretaria_initial = self.data.get("secretaria") or self.initial.get("secretaria") or getattr(self.instance, "secretaria_id", None)
        if secretaria_initial:
            self.fields["unidade"].queryset = unidades_qs.filter(secretaria_id=secretaria_initial)

    def clean(self):
        cleaned = super().clean()
        inicio = cleaned.get("data_inicio")
        fim = cleaned.get("data_fim")
        secretaria = cleaned.get("secretaria")
        unidade = cleaned.get("unidade")
        tipo = cleaned.get("tipo")
        dia_letivo = cleaned.get("dia_letivo")

        if inicio and fim and fim < inicio:
            self.add_error("data_fim", "A data final não pode ser anterior à data inicial.")

        if unidade and secretaria and unidade.secretaria_id != secretaria.id:
            self.add_error("unidade", "A unidade deve pertencer à secretaria selecionada.")

        if tipo in {
            CalendarioEducacionalEvento.Tipo.FERIADO,
            CalendarioEducacionalEvento.Tipo.RECESSO,
            CalendarioEducacionalEvento.Tipo.FACULTATIVO,
        } and dia_letivo:
            self.add_error("dia_letivo", "Feriado/Recesso/Facultativo não deve ser marcado como dia letivo.")

        return cleaned
