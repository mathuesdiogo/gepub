from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class ProcessoAdministrativo(models.Model):
    class Status(models.TextChoices):
        ABERTO = "ABERTO", "Aberto"
        EM_TRAMITACAO = "EM_TRAMITACAO", "Em tramitacao"
        CONCLUIDO = "CONCLUIDO", "Concluido"
        ARQUIVADO = "ARQUIVADO", "Arquivado"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="processos_admin")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="processos_admin",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="processos_admin",
        null=True,
        blank=True,
    )
    setor = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="processos_admin",
        null=True,
        blank=True,
    )

    numero = models.CharField(max_length=40)
    tipo = models.CharField(max_length=120)
    assunto = models.CharField(max_length=180)
    solicitante_nome = models.CharField(max_length=180, blank=True, default="")
    descricao = models.TextField(blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ABERTO)

    responsavel_atual = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processos_responsavel",
    )
    data_abertura = models.DateField(default=timezone.localdate)
    prazo_final = models.DateField(null=True, blank=True)

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processos_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Processo administrativo"
        verbose_name_plural = "Processos administrativos"
        ordering = ["-criado_em", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "numero"], name="uniq_processo_municipio_numero"),
        ]
        indexes = [
            models.Index(fields=["municipio", "status", "data_abertura"]),
            models.Index(fields=["tipo"]),
            models.Index(fields=["assunto"]),
        ]

    def __str__(self) -> str:
        return f"{self.numero} - {self.assunto}"


class ProcessoAndamento(models.Model):
    class Tipo(models.TextChoices):
        ENCAMINHAMENTO = "ENCAMINHAMENTO", "Encaminhamento"
        DESPACHO = "DESPACHO", "Despacho"
        CIENCIA = "CIENCIA", "Ciencia"
        CONCLUSAO = "CONCLUSAO", "Conclusao"

    processo = models.ForeignKey(ProcessoAdministrativo, on_delete=models.CASCADE, related_name="andamentos")
    tipo = models.CharField(max_length=16, choices=Tipo.choices, default=Tipo.ENCAMINHAMENTO)
    setor_origem = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="processos_origem",
        null=True,
        blank=True,
    )
    setor_destino = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="processos_destino",
        null=True,
        blank=True,
    )
    despacho = models.TextField(blank=True, default="")
    prazo = models.DateField(null=True, blank=True)
    data_evento = models.DateField(default=timezone.localdate)

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="andamentos_processo_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Andamento de processo"
        verbose_name_plural = "Andamentos de processo"
        ordering = ["-data_evento", "-id"]
        indexes = [
            models.Index(fields=["processo", "data_evento"]),
            models.Index(fields=["tipo"]),
        ]

    def __str__(self) -> str:
        return f"{self.processo.numero} - {self.get_tipo_display()}"
