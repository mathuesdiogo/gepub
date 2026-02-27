from __future__ import annotations

from django.conf import settings
from django.db import models


class ConversionJob(models.Model):
    class Tipo(models.TextChoices):
        DOCX_TO_PDF = "DOCX_TO_PDF", "DOCX -> PDF"
        IMG_TO_PDF = "IMG_TO_PDF", "Imagem -> PDF"
        PDF_TO_IMAGES = "PDF_TO_IMAGES", "PDF -> Imagens"
        PDF_MERGE = "PDF_MERGE", "Unir PDFs"
        PDF_SPLIT = "PDF_SPLIT", "Separar PDF"

    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        PROCESSANDO = "PROCESSANDO", "Processando"
        CONCLUIDO = "CONCLUIDO", "Concluído"
        ERRO = "ERRO", "Erro"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="conversao_jobs")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="conversao_jobs",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="conversao_jobs",
        null=True,
        blank=True,
    )
    setor = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="conversao_jobs",
        null=True,
        blank=True,
    )

    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.DOCX_TO_PDF)
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.PENDENTE)

    input_file = models.FileField(upload_to="conversor/input/%Y/%m/", blank=True, null=True)
    output_file = models.FileField(upload_to="conversor/output/%Y/%m/", blank=True, null=True)

    parametros_json = models.JSONField(default=dict, blank=True)
    logs = models.TextField(blank=True, default="")

    tamanho_entrada = models.PositiveIntegerField(default=0)
    tamanho_saida = models.PositiveIntegerField(default=0)
    duracao_ms = models.PositiveIntegerField(default=0)

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversao_jobs_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    concluido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Job de conversão"
        verbose_name_plural = "Jobs de conversão"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["municipio", "status", "criado_em"]),
            models.Index(fields=["tipo", "status", "criado_em"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} • {self.get_status_display()}"


class ConversionJobInput(models.Model):
    job = models.ForeignKey(ConversionJob, on_delete=models.CASCADE, related_name="inputs")
    arquivo = models.FileField(upload_to="conversor/input/%Y/%m/")
    ordem = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Arquivo adicional do job"
        verbose_name_plural = "Arquivos adicionais do job"
        ordering = ["ordem", "id"]

    def __str__(self) -> str:
        return f"{self.job_id} • {self.arquivo.name}"
