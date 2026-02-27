from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class TributosCadastro(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        INATIVO = "INATIVO", "Inativo"

    class TipoPessoa(models.TextChoices):
        PF = "PF", "Pessoa Física"
        PJ = "PJ", "Pessoa Jurídica"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="tributos_cadastros")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="tributos_cadastros",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="tributos_cadastros",
        null=True,
        blank=True,
    )
    setor = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="tributos_cadastros",
        null=True,
        blank=True,
    )

    codigo = models.CharField(max_length=40)
    nome = models.CharField(max_length=180, verbose_name="Contribuinte")
    documento = models.CharField(max_length=20, blank=True, default="", help_text="CPF/CNPJ")
    tipo_pessoa = models.CharField(max_length=2, choices=TipoPessoa.choices, default=TipoPessoa.PF)
    inscricao_municipal = models.CharField(max_length=40, blank=True, default="")
    endereco = models.TextField(blank=True, default="")
    email = models.EmailField(blank=True, default="")
    telefone = models.CharField(max_length=40, blank=True, default="")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ATIVO)
    observacao = models.TextField(blank=True, default="")

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tributos_cadastros_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Contribuinte"
        verbose_name_plural = "Contribuintes"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "codigo"], name="uniq_tributos_cadastro_municipio_codigo"),
            models.UniqueConstraint(
                fields=["municipio", "inscricao_municipal"],
                condition=~models.Q(inscricao_municipal=""),
                name="uniq_tributos_inscricao_municipio",
            ),
        ]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["codigo"]),
            models.Index(fields=["documento"]),
            models.Index(fields=["nome"]),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} - {self.nome}"


class TributoLancamento(models.Model):
    class TipoTributo(models.TextChoices):
        IPTU = "IPTU", "IPTU"
        ISS = "ISS", "ISS"
        ITBI = "ITBI", "ITBI"
        TAXA = "TAXA", "Taxa"

    class Status(models.TextChoices):
        EMITIDO = "EMITIDO", "Emitido"
        PAGO = "PAGO", "Pago"
        PARCELADO = "PARCELADO", "Parcelado"
        CANCELADO = "CANCELADO", "Cancelado"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="tributos_lancamentos")
    contribuinte = models.ForeignKey(TributosCadastro, on_delete=models.CASCADE, related_name="lancamentos")
    tipo_tributo = models.CharField(max_length=10, choices=TipoTributo.choices, default=TipoTributo.IPTU)
    exercicio = models.PositiveIntegerField(default=timezone.localdate().year)
    competencia = models.CharField(max_length=7, blank=True, default="", help_text="YYYY-MM opcional")
    referencia = models.CharField(max_length=40, blank=True, default="")
    valor_principal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    multa = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    juros = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    desconto = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    valor_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    data_vencimento = models.DateField(default=timezone.localdate)
    data_pagamento = models.DateField(null=True, blank=True)
    banco_recebedor = models.CharField(max_length=80, blank=True, default="")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.EMITIDO)
    observacao = models.TextField(blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tributos_lancamentos_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lançamento tributário"
        verbose_name_plural = "Lançamentos tributários"
        ordering = ["-exercicio", "-id"]
        indexes = [
            models.Index(fields=["municipio", "tipo_tributo", "status"]),
            models.Index(fields=["contribuinte", "exercicio"]),
        ]

    def save(self, *args, **kwargs):
        self.valor_total = (self.valor_principal or 0) + (self.multa or 0) + (self.juros or 0) - (self.desconto or 0)
        if self.status == self.Status.PAGO and not self.data_pagamento:
            self.data_pagamento = timezone.localdate()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.contribuinte.nome} • {self.get_tipo_tributo_display()} • {self.exercicio}"
