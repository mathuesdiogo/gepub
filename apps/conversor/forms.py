from __future__ import annotations

import os
import re

from django import forms
from django.conf import settings

from .models import ConversionJob


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        single_clean = super().clean
        if not data:
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]

        cleaned = []
        for item in data:
            cleaned.append(single_clean(item, initial))
        return cleaned


class ConversionJobForm(forms.ModelForm):
    arquivos_adicionais = MultipleFileField(
        required=False,
        widget=MultipleFileInput(attrs={"multiple": True}),
        help_text="Use para merge de PDFs ou múltiplas imagens para PDF.",
    )
    pages = forms.CharField(
        required=False,
        label="Páginas (split)",
        help_text="Ex.: 1-3,7,10",
    )

    class Meta:
        model = ConversionJob
        fields = [
            "tipo",
            "input_file",
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

    def _ext(self, filename: str) -> str:
        return os.path.splitext((filename or "").lower())[1]

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo")
        primary = cleaned.get("input_file")
        extras = cleaned.get("arquivos_adicionais") or []
        files = [f for f in [primary, *extras] if f]

        if not files:
            self.add_error("input_file", "Envie ao menos um arquivo para conversão.")
            return cleaned

        max_mb = int(getattr(settings, "CONVERSOR_MAX_UPLOAD_MB", 80))
        max_size = max_mb * 1024 * 1024
        total_size = sum(getattr(f, "size", 0) for f in files)
        if total_size > max_size:
            self.add_error("input_file", f"Tamanho total excede {max_mb} MB.")

        doc_ext = {".docx", ".doc"}
        img_ext = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
        pdf_ext = {".pdf"}

        file_exts = [self._ext(getattr(f, "name", "")) for f in files]

        if tipo == ConversionJob.Tipo.DOCX_TO_PDF:
            if not primary or self._ext(primary.name) not in doc_ext:
                self.add_error("input_file", "Para DOCX -> PDF, envie .docx ou .doc no arquivo principal.")

        if tipo == ConversionJob.Tipo.IMG_TO_PDF:
            if any(ext not in img_ext for ext in file_exts):
                self.add_error("input_file", "Para Imagem -> PDF, envie apenas arquivos de imagem.")

        if tipo in {ConversionJob.Tipo.PDF_TO_IMAGES, ConversionJob.Tipo.PDF_SPLIT}:
            if not primary or self._ext(primary.name) not in pdf_ext:
                self.add_error("input_file", "Para esta conversão, o arquivo principal deve ser PDF.")

        if tipo == ConversionJob.Tipo.PDF_MERGE:
            if len(files) < 2:
                self.add_error("arquivos_adicionais", "Para unir PDFs, envie ao menos dois arquivos PDF.")
            if any(ext not in pdf_ext for ext in file_exts):
                self.add_error("input_file", "No merge, todos os arquivos devem ser PDF.")

        pages = (cleaned.get("pages") or "").strip()
        if pages and not re.match(r"^[0-9,\-\s]+$", pages):
            self.add_error("pages", "Formato inválido. Use apenas números, vírgula e hífen (ex.: 1-3,8).")

        cleaned["arquivos_adicionais_list"] = extras
        cleaned["parametros_json"] = {"pages": pages}
        cleaned["total_size"] = total_size
        return cleaned
