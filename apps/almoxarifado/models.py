from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class AlmoxarifadoCadastro(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        INATIVO = "INATIVO", "Inativo"

    class UnidadeMedida(models.TextChoices):
        UN = "UN", "Unidade"
        CX = "CX", "Caixa"
        KG = "KG", "Quilo"
        LT = "LT", "Litro"
        MT = "MT", "Metro"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="almoxarifado_cadastros")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="almoxarifado_cadastros",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="almoxarifado_cadastros",
        null=True,
        blank=True,
    )
    setor = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="almoxarifado_cadastros",
        null=True,
        blank=True,
    )

    codigo = models.CharField(max_length=40)
    nome = models.CharField(max_length=180)
    unidade_medida = models.CharField(max_length=4, choices=UnidadeMedida.choices, default=UnidadeMedida.UN)
    estoque_minimo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    saldo_atual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_medio = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ATIVO)
    observacao = models.TextField(blank=True, default="")

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="almoxarifado_cadastros_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Item de estoque"
        verbose_name_plural = "Itens de estoque"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "codigo"], name="uniq_almoxarifado_cadastro_municipio_codigo"),
        ]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["codigo"]),
            models.Index(fields=["nome"]),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} - {self.nome}"


class AlmoxarifadoMovimento(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = "ENTRADA", "Entrada"
        SAIDA = "SAIDA", "Saída"
        AJUSTE = "AJUSTE", "Ajuste"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="almoxarifado_movimentos")
    item = models.ForeignKey(AlmoxarifadoCadastro, on_delete=models.CASCADE, related_name="movimentos")
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.ENTRADA)
    data_movimento = models.DateField(default=timezone.localdate)
    quantidade = models.DecimalField(max_digits=12, decimal_places=2)
    valor_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    documento = models.CharField(max_length=60, blank=True, default="")
    observacao = models.TextField(blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="almoxarifado_movimentos_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Movimento de estoque"
        verbose_name_plural = "Movimentos de estoque"
        ordering = ["-data_movimento", "-id"]
        indexes = [
            models.Index(fields=["municipio", "tipo"]),
            models.Index(fields=["item", "data_movimento"]),
        ]

    def __str__(self):
        return f"{self.item.codigo} • {self.get_tipo_display()} • {self.quantidade}"


class AlmoxarifadoRequisicao(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        APROVADA = "APROVADA", "Aprovada"
        ATENDIDA = "ATENDIDA", "Atendida"
        CANCELADA = "CANCELADA", "Cancelada"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="almoxarifado_requisicoes")
    numero = models.CharField(max_length=40)
    item = models.ForeignKey(AlmoxarifadoCadastro, on_delete=models.PROTECT, related_name="requisicoes")
    secretaria_solicitante = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="almoxarifado_requisicoes",
        null=True,
        blank=True,
    )
    unidade_solicitante = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="almoxarifado_requisicoes",
        null=True,
        blank=True,
    )
    setor_solicitante = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="almoxarifado_requisicoes",
        null=True,
        blank=True,
    )
    quantidade = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    justificativa = models.TextField(blank=True, default="")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDENTE)
    aprovado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="almoxarifado_requisicoes_aprovadas",
    )
    aprovado_em = models.DateTimeField(null=True, blank=True)
    atendido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="almoxarifado_requisicoes_atendidas",
    )
    atendido_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="almoxarifado_requisicoes_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Requisição de almoxarifado"
        verbose_name_plural = "Requisições de almoxarifado"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "numero"], name="uniq_almoxarifado_req_municipio_numero"),
        ]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["item", "status"]),
        ]

    def __str__(self):
        return f"{self.numero} • {self.item.codigo} • {self.get_status_display()}"
