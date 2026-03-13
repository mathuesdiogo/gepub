from __future__ import annotations

from django import forms

from apps.core.models import OperacaoRegistroAnexo, OperacaoRegistroComentario, OperacaoRegistroTag


class OperacaoRegistroTagForm(forms.ModelForm):
    class Meta:
        model = OperacaoRegistroTag
        fields = ["tag"]

    def clean_tag(self):
        return (self.cleaned_data.get("tag") or "").strip()


class OperacaoRegistroComentarioForm(forms.ModelForm):
    class Meta:
        model = OperacaoRegistroComentario
        fields = ["comentario", "interno"]

    def clean_comentario(self):
        return (self.cleaned_data.get("comentario") or "").strip()


class OperacaoRegistroAnexoForm(forms.ModelForm):
    class Meta:
        model = OperacaoRegistroAnexo
        fields = ["tipo", "titulo", "observacao", "arquivo"]

    def clean_tipo(self):
        return (self.cleaned_data.get("tipo") or "").strip()

    def clean_titulo(self):
        return (self.cleaned_data.get("titulo") or "").strip()

    def clean_observacao(self):
        return (self.cleaned_data.get("observacao") or "").strip()
