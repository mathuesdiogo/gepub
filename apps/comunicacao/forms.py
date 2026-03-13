from __future__ import annotations

from django import forms

from .models import NotificationChannelConfig, NotificationTemplate


class NotificationChannelConfigForm(forms.ModelForm):
    class Meta:
        model = NotificationChannelConfig
        fields = [
            "secretaria",
            "unidade",
            "channel",
            "provider",
            "sender_name",
            "sender_identifier",
            "credentials_json",
            "options_json",
            "is_active",
            "prioridade",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["secretaria"].queryset = self.fields["secretaria"].queryset.filter(municipio=municipio)
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(secretaria__municipio=municipio)


class NotificationTemplateForm(forms.ModelForm):
    class Meta:
        model = NotificationTemplate
        fields = [
            "scope",
            "secretaria",
            "unidade",
            "event_key",
            "channel",
            "nome",
            "subject",
            "body",
            "is_active",
            "nee_safe",
        ]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 8}),
            "subject": forms.TextInput(attrs={"placeholder": "Obrigatório para e-mail"}),
        }

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["secretaria"].queryset = self.fields["secretaria"].queryset.filter(municipio=municipio)
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(secretaria__municipio=municipio)

    def clean(self):
        cleaned = super().clean()
        scope = cleaned.get("scope")
        secretaria = cleaned.get("secretaria")
        unidade = cleaned.get("unidade")

        if scope == NotificationTemplate.Scope.MUNICIPIO:
            cleaned["secretaria"] = None
            cleaned["unidade"] = None
        elif scope == NotificationTemplate.Scope.SECRETARIA:
            if not secretaria:
                self.add_error("secretaria", "Selecione a secretaria para escopo de secretaria.")
            cleaned["unidade"] = None
        elif scope == NotificationTemplate.Scope.UNIDADE:
            if not unidade:
                self.add_error("unidade", "Selecione a unidade para escopo de unidade.")
            if unidade and secretaria and unidade.secretaria_id != secretaria.id:
                self.add_error("unidade", "A unidade deve pertencer à secretaria selecionada.")
        return cleaned
