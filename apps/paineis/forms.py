from __future__ import annotations

from django import forms
from django.conf import settings

from .models import Dataset


class DatasetCreateForm(forms.ModelForm):
    arquivo = forms.FileField(
        required=False,
        help_text="Formatos fortes: CSV e XLSX. PDF/DOCX são condicionais.",
    )
    google_sheet_url = forms.URLField(
        required=False,
        label="URL Google Sheets (CSV)",
        help_text="Use link de exportação CSV ou planilha pública.",
    )

    class Meta:
        model = Dataset
        fields = [
            "nome",
            "descricao",
            "categoria",
            "fonte",
            "visibilidade",
            "secretaria",
            "unidade",
            "setor",
        ]

    def __init__(self, *args, municipio=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.municipio = municipio
        self.user = user

        if municipio is not None:
            self.fields["secretaria"].queryset = self.fields["secretaria"].queryset.filter(municipio=municipio)
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(secretaria__municipio=municipio)
            self.fields["setor"].queryset = self.fields["setor"].queryset.filter(unidade__secretaria__municipio=municipio)

    def clean(self):
        cleaned = super().clean()
        fonte = cleaned.get("fonte")
        arquivo = cleaned.get("arquivo")
        sheet_url = (cleaned.get("google_sheet_url") or "").strip()

        max_mb = int(getattr(settings, "PAINEIS_MAX_UPLOAD_MB", 50))
        max_size = max_mb * 1024 * 1024

        if fonte == Dataset.Fonte.GOOGLE_SHEETS:
            if not sheet_url:
                self.add_error("google_sheet_url", "Informe a URL pública CSV da planilha.")
        else:
            if not arquivo:
                self.add_error("arquivo", "Envie um arquivo para ingestão do dataset.")
            elif arquivo.size > max_size:
                self.add_error("arquivo", f"Arquivo excede o limite de {max_mb} MB.")

        if arquivo and fonte == Dataset.Fonte.CSV:
            name = (arquivo.name or "").lower()
            if not name.endswith(".csv") and not name.endswith(".txt"):
                self.add_error("arquivo", "Para fonte CSV, envie arquivo .csv ou .txt.")

        if arquivo and fonte == Dataset.Fonte.XLSX:
            name = (arquivo.name or "").lower()
            if not name.endswith(".xlsx"):
                self.add_error("arquivo", "Para fonte XLSX, envie arquivo .xlsx.")

        return cleaned
