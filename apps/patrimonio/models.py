from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class PatrimonioCadastro(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        INATIVO = "INATIVO", "Inativo"

    class Categoria(models.TextChoices):
        IMOVEL = "IMOVEL", "Imóvel"
        MOVEL = "MOVEL", "Móvel"
        INFORMATICA = "INFORMATICA", "Informática"
        VEICULO = "VEICULO", "Veículo"
        OUTRO = "OUTRO", "Outro"

    class Situacao(models.TextChoices):
        EM_USO = "EM_USO", "Em uso"
        ESTOQUE = "ESTOQUE", "Em estoque"
        MANUTENCAO = "MANUTENCAO", "Em manutenção"
        BAIXADO = "BAIXADO", "Baixado"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="patrimonio_cadastros")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="patrimonio_cadastros",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="patrimonio_cadastros",
        null=True,
        blank=True,
    )
    setor = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="patrimonio_cadastros",
        null=True,
        blank=True,
    )

    codigo = models.CharField(max_length=40)
    tombo = models.CharField(max_length=40, blank=True, default="")
    nome = models.CharField(max_length=180)
    categoria = models.CharField(max_length=20, choices=Categoria.choices, default=Categoria.MOVEL)
    situacao = models.CharField(max_length=20, choices=Situacao.choices, default=Situacao.EM_USO)
    data_aquisicao = models.DateField(default=timezone.localdate)
    valor_aquisicao = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    estado_conservacao = models.CharField(max_length=40, blank=True, default="Bom")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ATIVO)
    observacao = models.TextField(blank=True, default="")

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="patrimonio_cadastros_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bem patrimonial"
        verbose_name_plural = "Bens patrimoniais"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "codigo"], name="uniq_patrimonio_cadastro_municipio_codigo"),
            models.UniqueConstraint(
                fields=["municipio", "tombo"],
                condition=~models.Q(tombo=""),
                name="uniq_patrimonio_tombo_municipio",
            ),
        ]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["municipio", "situacao"]),
            models.Index(fields=["codigo"]),
            models.Index(fields=["tombo"]),
            models.Index(fields=["nome"]),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} - {self.nome}"


class PatrimonioMovimentacao(models.Model):
    class Tipo(models.TextChoices):
        TRANSFERENCIA = "TRANSFERENCIA", "Transferência"
        MANUTENCAO = "MANUTENCAO", "Manutenção"
        BAIXA = "BAIXA", "Baixa"
        INVENTARIO = "INVENTARIO", "Inventário"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="patrimonio_movimentacoes")
    bem = models.ForeignKey(PatrimonioCadastro, on_delete=models.CASCADE, related_name="movimentacoes")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.TRANSFERENCIA)
    data_movimento = models.DateField(default=timezone.localdate)
    unidade_origem = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="patrimonio_movimentacoes_origem",
        null=True,
        blank=True,
    )
    unidade_destino = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="patrimonio_movimentacoes_destino",
        null=True,
        blank=True,
    )
    valor_movimento = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    observacao = models.TextField(blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="patrimonio_movimentacoes_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Movimentação patrimonial"
        verbose_name_plural = "Movimentações patrimoniais"
        ordering = ["-data_movimento", "-id"]
        indexes = [
            models.Index(fields=["municipio", "tipo"]),
            models.Index(fields=["bem", "data_movimento"]),
        ]

    def __str__(self):
        return f"{self.bem.nome} • {self.get_tipo_display()} • {self.data_movimento}"


class PatrimonioInventario(models.Model):
    class Status(models.TextChoices):
        ABERTO = "ABERTO", "Aberto"
        CONCLUIDO = "CONCLUIDO", "Concluído"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="patrimonio_inventarios")
    codigo = models.CharField(max_length=40)
    referencia = models.CharField(max_length=120, blank=True, default="")
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="patrimonio_inventarios",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ABERTO)
    total_bens = models.PositiveIntegerField(default=0)
    total_bens_ativos = models.PositiveIntegerField(default=0)
    observacao = models.TextField(blank=True, default="")
    concluido_em = models.DateTimeField(null=True, blank=True)
    concluido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="patrimonio_inventarios_concluidos",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="patrimonio_inventarios_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Inventário patrimonial"
        verbose_name_plural = "Inventários patrimoniais"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "codigo"], name="uniq_patrimonio_inventario_municipio_codigo"),
        ]
        indexes = [
            models.Index(fields=["municipio", "status"]),
        ]

    def __str__(self):
        return f"{self.codigo} • {self.get_status_display()}"
