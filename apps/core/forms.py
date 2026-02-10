# apps/core/forms.py
from __future__ import annotations

from django import forms

from .models import AlunoAviso, AlunoArquivo


class AlunoAvisoForm(forms.ModelForm):
    class Meta:
        model = AlunoAviso
        fields = [
            "titulo",
            "texto",
            "aluno",
            "turma",
            "unidade",
            "secretaria",
            "municipio",
            "ativo",
        ]


class AlunoArquivoForm(forms.ModelForm):
    class Meta:
        model = AlunoArquivo
        fields = [
            "titulo",
            "descricao",
            "arquivo",
            "aluno",
            "turma",
            "unidade",
            "secretaria",
            "municipio",
            "ativo",
        ]
