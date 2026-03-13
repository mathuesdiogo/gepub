from __future__ import annotations

from urllib.parse import urlparse

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
        self.fields["nome"].widget.attrs.update(
            {
                "class": "bi-input",
                "placeholder": "Ex.: Produção da Atenção Básica 2026",
            }
        )
        self.fields["descricao"].widget.attrs.update(
            {
                "class": "bi-input",
                "rows": 3,
                "placeholder": "Descreva a origem e o objetivo analítico deste dataset.",
            }
        )
        self.fields["categoria"].widget.attrs.update(
            {
                "class": "bi-input",
                "placeholder": "Ex.: Saúde, Educação, Financeiro",
            }
        )
        self.fields["fonte"].widget.attrs.update({"class": "bi-input", "data-bi-fonte": "1"})
        self.fields["visibilidade"].widget.attrs.update({"class": "bi-input"})
        self.fields["secretaria"].widget.attrs.update({"class": "bi-input"})
        self.fields["unidade"].widget.attrs.update({"class": "bi-input"})
        self.fields["setor"].widget.attrs.update({"class": "bi-input"})
        self.fields["arquivo"].widget.attrs.update(
            {
                "class": "bi-input",
                "accept": ".csv,.txt,.xlsx",
            }
        )
        self.fields["google_sheet_url"].widget.attrs.update(
            {
                "class": "bi-input",
                "placeholder": "https://docs.google.com/spreadsheets/d/.../edit#gid=0",
            }
        )

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
                parsed = urlparse(sheet_url)
                host = (parsed.hostname or "").lower()
                if parsed.scheme.lower() != "https" or host != "docs.google.com" or not (parsed.path or "").startswith("/spreadsheets/"):
                    self.add_error(
                        "google_sheet_url",
                        "Informe uma URL HTTPS válida do Google Sheets (docs.google.com/spreadsheets/...).",
                    )
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
