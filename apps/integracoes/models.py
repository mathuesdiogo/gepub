from __future__ import annotations

from django.conf import settings
from django.db import models


class ConectorIntegracao(models.Model):
    class Dominio(models.TextChoices):
        FINANCEIRO = "FINANCEIRO", "Financeiro"
        EDUCACAO = "EDUCACAO", "Educacao"
        SAUDE = "SAUDE", "Saude"
        TRANSPARENCIA = "TRANSPARENCIA", "Transparencia"
        GOVBR = "GOVBR", "Gov.br"
        SICONFI = "SICONFI", "SICONFI"
        OUTROS = "OUTROS", "Outros"

    class Tipo(models.TextChoices):
        API = "API", "API"
        ARQUIVO = "ARQUIVO", "Arquivo"
        ETL = "ETL", "ETL"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="integracoes_conectores")
    nome = models.CharField(max_length=140)
    dominio = models.CharField(max_length=20, choices=Dominio.choices, default=Dominio.OUTROS)
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.API)
    endpoint = models.CharField(max_length=255, blank=True, default="")
    credenciais = models.JSONField(default=dict, blank=True)
    configuracao = models.JSONField(default=dict, blank=True)
    ativo = models.BooleanField(default=True)

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conectores_integracao_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Conector de integracao"
        verbose_name_plural = "Conectores de integracao"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "nome"], name="uniq_integracao_conector_municipio_nome"),
        ]

    def __str__(self) -> str:
        return self.nome


class IntegracaoExecucao(models.Model):
    class Direcao(models.TextChoices):
        IMPORTACAO = "IMPORTACAO", "Importacao"
        EXPORTACAO = "EXPORTACAO", "Exportacao"

    class Status(models.TextChoices):
        SUCESSO = "SUCESSO", "Sucesso"
        FALHA = "FALHA", "Falha"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="integracoes_execucoes")
    conector = models.ForeignKey(ConectorIntegracao, on_delete=models.CASCADE, related_name="execucoes")
    direcao = models.CharField(max_length=12, choices=Direcao.choices, default=Direcao.IMPORTACAO)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SUCESSO)
    referencia = models.CharField(max_length=120, blank=True, default="")
    quantidade_registros = models.PositiveIntegerField(default=0)
    detalhes = models.TextField(blank=True, default="")

    executado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="integracoes_executadas",
    )
    executado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Execucao de integracao"
        verbose_name_plural = "Execucoes de integracao"
        ordering = ["-executado_em", "-id"]
        indexes = [
            models.Index(fields=["municipio", "status", "executado_em"]),
            models.Index(fields=["conector", "executado_em"]),
        ]

    def __str__(self) -> str:
        return f"{self.conector.nome} - {self.get_status_display()}"
