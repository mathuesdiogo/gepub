from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class ContratoAdministrativo(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        SUSPENSO = "SUSPENSO", "Suspenso"
        ENCERRADO = "ENCERRADO", "Encerrado"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="contratos_admin")
    processo_licitatorio = models.ForeignKey(
        "compras.ProcessoLicitatorio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contratos",
    )
    requisicao_compra = models.ForeignKey(
        "compras.RequisicaoCompra",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contratos",
    )

    numero = models.CharField(max_length=40)
    objeto = models.CharField(max_length=240)
    fornecedor_nome = models.CharField(max_length=180)
    fornecedor_documento = models.CharField(max_length=30, blank=True, default="")
    fiscal_nome = models.CharField(max_length=160, blank=True, default="")

    valor_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    vigencia_inicio = models.DateField(default=timezone.localdate)
    vigencia_fim = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ATIVO)

    empenho = models.ForeignKey(
        "financeiro.DespEmpenho",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contratos",
    )

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contratos_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Contrato administrativo"
        verbose_name_plural = "Contratos administrativos"
        ordering = ["-vigencia_inicio", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "numero"], name="uniq_contrato_municipio_numero"),
        ]
        indexes = [
            models.Index(fields=["municipio", "status", "vigencia_fim"]),
        ]

    def __str__(self) -> str:
        return f"{self.numero} - {self.objeto}"


class AditivoContrato(models.Model):
    class Tipo(models.TextChoices):
        PRAZO = "PRAZO", "Prazo"
        VALOR = "VALOR", "Valor"
        ESCOPO = "ESCOPO", "Escopo"

    contrato = models.ForeignKey(ContratoAdministrativo, on_delete=models.CASCADE, related_name="aditivos")
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    numero = models.CharField(max_length=40)
    data_ato = models.DateField(default=timezone.localdate)
    valor_aditivo = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    nova_vigencia_fim = models.DateField(null=True, blank=True)
    descricao = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Aditivo contratual"
        verbose_name_plural = "Aditivos contratuais"
        ordering = ["-data_ato", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["contrato", "numero"], name="uniq_aditivo_contrato_numero"),
        ]

    def __str__(self) -> str:
        return f"{self.contrato.numero} - {self.numero}"


class MedicaoContrato(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        ATESTADA = "ATESTADA", "Atestada"
        LIQUIDADA = "LIQUIDADA", "Liquidada"

    contrato = models.ForeignKey(ContratoAdministrativo, on_delete=models.CASCADE, related_name="medicoes")
    numero = models.CharField(max_length=40)
    competencia = models.CharField(max_length=7, help_text="Formato YYYY-MM")
    data_medicao = models.DateField(default=timezone.localdate)
    valor_medido = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    observacao = models.TextField(blank=True, default="")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDENTE)

    atestado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="medicoes_atestadas",
    )
    atestado_em = models.DateTimeField(null=True, blank=True)

    liquidacao = models.ForeignKey(
        "financeiro.DespLiquidacao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="medicoes_contrato",
    )

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="medicoes_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Medicao contratual"
        verbose_name_plural = "Medicoes contratuais"
        ordering = ["-data_medicao", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["contrato", "numero"], name="uniq_medicao_contrato_numero"),
        ]

    def __str__(self) -> str:
        return f"{self.contrato.numero} - medicao {self.numero}"
