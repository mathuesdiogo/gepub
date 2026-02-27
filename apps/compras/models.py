from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class RequisicaoCompra(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        EM_APROVACAO = "EM_APROVACAO", "Em aprovacao"
        APROVADA = "APROVADA", "Aprovada"
        REPROVADA = "REPROVADA", "Reprovada"
        HOMOLOGADA = "HOMOLOGADA", "Homologada"
        CANCELADA = "CANCELADA", "Cancelada"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="compras_requisicoes")
    processo = models.ForeignKey(
        "processos.ProcessoAdministrativo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requisicoes_compra",
    )
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="compras_requisicoes",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="compras_requisicoes",
        null=True,
        blank=True,
    )
    setor = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="compras_requisicoes",
        null=True,
        blank=True,
    )

    numero = models.CharField(max_length=40)
    objeto = models.CharField(max_length=220)
    justificativa = models.TextField(blank=True, default="")
    valor_estimado = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    data_necessidade = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RASCUNHO)

    fornecedor_nome = models.CharField(max_length=180, blank=True, default="")
    fornecedor_documento = models.CharField(max_length=30, blank=True, default="")

    dotacao = models.ForeignKey(
        "financeiro.OrcDotacao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="requisicoes_compra",
    )
    empenho = models.ForeignKey(
        "financeiro.DespEmpenho",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requisicoes_compra",
    )

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="compras_requisicoes_criadas",
    )
    aprovado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="compras_requisicoes_aprovadas",
    )
    aprovado_em = models.DateTimeField(null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Requisicao de compra"
        verbose_name_plural = "Requisicoes de compra"
        ordering = ["-criado_em", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "numero"], name="uniq_compra_req_municipio_numero"),
        ]
        indexes = [
            models.Index(fields=["municipio", "status", "criado_em"]),
            models.Index(fields=["objeto"]),
        ]

    @property
    def valor_itens(self) -> Decimal:
        agg = self.itens.aggregate(total=models.Sum("valor_total"))
        return agg.get("total") or Decimal("0.00")

    def __str__(self) -> str:
        return f"{self.numero} - {self.objeto}"


class RequisicaoCompraItem(models.Model):
    requisicao = models.ForeignKey(RequisicaoCompra, on_delete=models.CASCADE, related_name="itens")
    descricao = models.CharField(max_length=220)
    unidade_medida = models.CharField(max_length=20, blank=True, default="UN")
    quantidade = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("1.00"))
    valor_unitario = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    valor_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        verbose_name = "Item da requisicao"
        verbose_name_plural = "Itens da requisicao"
        ordering = ["id"]

    def save(self, *args, **kwargs):
        self.valor_total = (self.quantidade or Decimal("0.00")) * (self.valor_unitario or Decimal("0.00"))
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.descricao


class ProcessoLicitatorio(models.Model):
    class Modalidade(models.TextChoices):
        PREGAO = "PREGAO", "Pregao"
        CONCORRENCIA = "CONCORRENCIA", "Concorrencia"
        DISPENSA = "DISPENSA", "Dispensa"
        INEXIGIBILIDADE = "INEXIGIBILIDADE", "Inexigibilidade"

    class Status(models.TextChoices):
        PLANEJAMENTO = "PLANEJAMENTO", "Planejamento"
        EM_CURSO = "EM_CURSO", "Em curso"
        HOMOLOGADO = "HOMOLOGADO", "Homologado"
        FRACASSADO = "FRACASSADO", "Fracassado"
        REVOGADO = "REVOGADO", "Revogado"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="compras_licitacoes")
    requisicao = models.ForeignKey(
        RequisicaoCompra,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="licitacoes",
    )
    numero_processo = models.CharField(max_length=40)
    modalidade = models.CharField(max_length=20, choices=Modalidade.choices)
    objeto = models.CharField(max_length=220)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANEJAMENTO)
    data_abertura = models.DateField(default=timezone.localdate)
    vencedor_nome = models.CharField(max_length=180, blank=True, default="")

    class Meta:
        verbose_name = "Processo licitatorio"
        verbose_name_plural = "Processos licitatorios"
        ordering = ["-data_abertura", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "numero_processo"], name="uniq_compra_proc_municipio_numero"),
        ]

    def __str__(self) -> str:
        return f"{self.numero_processo} - {self.get_modalidade_display()}"
