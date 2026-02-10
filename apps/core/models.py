# apps/core/models.py
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class AlunoAviso(models.Model):
    """
    Avisos que aparecem no dashboard do aluno.
    Escopo (um ou mais):
    - aluno (direto)
    - turma
    - unidade
    - secretaria
    - municipio
    """

    titulo = models.CharField(max_length=160)
    texto = models.TextField(blank=True)
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="avisos_criados"
    )

    aluno = models.ForeignKey("educacao.Aluno", on_delete=models.CASCADE, null=True, blank=True, related_name="avisos")
    turma = models.ForeignKey("educacao.Turma", on_delete=models.CASCADE, null=True, blank=True, related_name="avisos")

    unidade = models.ForeignKey("org.Unidade", on_delete=models.CASCADE, null=True, blank=True, related_name="avisos")
    secretaria = models.ForeignKey("org.Secretaria", on_delete=models.CASCADE, null=True, blank=True, related_name="avisos")
    municipio = models.ForeignKey("org.Municipio", on_delete=models.CASCADE, null=True, blank=True, related_name="avisos")

    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return self.titulo


class AlunoArquivo(models.Model):
    """
    Arquivos anexados (atividades/documentos) para o aluno.
    Mesmo escopo do aviso.
    """

    titulo = models.CharField(max_length=160)
    descricao = models.TextField(blank=True)
    arquivo = models.FileField(upload_to="portal_aluno/")

    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="arquivos_criados"
    )

    aluno = models.ForeignKey("educacao.Aluno", on_delete=models.CASCADE, null=True, blank=True, related_name="arquivos")
    turma = models.ForeignKey("educacao.Turma", on_delete=models.CASCADE, null=True, blank=True, related_name="arquivos")

    unidade = models.ForeignKey("org.Unidade", on_delete=models.CASCADE, null=True, blank=True, related_name="arquivos")
    secretaria = models.ForeignKey("org.Secretaria", on_delete=models.CASCADE, null=True, blank=True, related_name="arquivos")
    municipio = models.ForeignKey("org.Municipio", on_delete=models.CASCADE, null=True, blank=True, related_name="arquivos")

    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return self.titulo
