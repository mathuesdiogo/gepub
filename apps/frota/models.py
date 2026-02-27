from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class FrotaCadastro(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        INATIVO = "INATIVO", "Inativo"

    class Situacao(models.TextChoices):
        DISPONIVEL = "DISPONIVEL", "Disponível"
        MANUTENCAO = "MANUTENCAO", "Em manutenção"
        INDISPONIVEL = "INDISPONIVEL", "Indisponível"
        BAIXADO = "BAIXADO", "Baixado"

    class Combustivel(models.TextChoices):
        GASOLINA = "GASOLINA", "Gasolina"
        DIESEL = "DIESEL", "Diesel"
        ETANOL = "ETANOL", "Etanol"
        FLEX = "FLEX", "Flex"
        ELETRICO = "ELETRICO", "Elétrico"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="frota_cadastros")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="frota_cadastros",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="frota_cadastros",
        null=True,
        blank=True,
    )
    setor = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="frota_cadastros",
        null=True,
        blank=True,
    )

    codigo = models.CharField(max_length=40)
    placa = models.CharField(max_length=12, blank=True, default="")
    nome = models.CharField(max_length=180)
    marca_modelo = models.CharField(max_length=120, blank=True, default="")
    ano_fabricacao = models.PositiveIntegerField(default=timezone.localdate().year)
    combustivel = models.CharField(max_length=12, choices=Combustivel.choices, default=Combustivel.FLEX)
    quilometragem_atual = models.PositiveIntegerField(default=0)
    situacao = models.CharField(max_length=15, choices=Situacao.choices, default=Situacao.DISPONIVEL)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ATIVO)
    observacao = models.TextField(blank=True, default="")

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="frota_cadastros_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Veículo da frota"
        verbose_name_plural = "Veículos da frota"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "codigo"], name="uniq_frota_cadastro_municipio_codigo"),
            models.UniqueConstraint(
                fields=["municipio", "placa"],
                condition=~models.Q(placa=""),
                name="uniq_frota_placa_municipio",
            ),
        ]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["municipio", "situacao"]),
            models.Index(fields=["codigo"]),
            models.Index(fields=["placa"]),
            models.Index(fields=["nome"]),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} - {self.nome}"


class FrotaAbastecimento(models.Model):
    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="frota_abastecimentos")
    veiculo = models.ForeignKey(FrotaCadastro, on_delete=models.CASCADE, related_name="abastecimentos")
    data_abastecimento = models.DateField(default=timezone.localdate)
    litros = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quilometragem = models.PositiveIntegerField(default=0)
    posto = models.CharField(max_length=120, blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="frota_abastecimentos_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Abastecimento"
        verbose_name_plural = "Abastecimentos"
        ordering = ["-data_abastecimento", "-id"]
        indexes = [
            models.Index(fields=["municipio", "data_abastecimento"]),
            models.Index(fields=["veiculo", "data_abastecimento"]),
        ]

    def __str__(self):
        return f"{self.veiculo.placa or self.veiculo.codigo} • {self.data_abastecimento}"


class FrotaManutencao(models.Model):
    class Tipo(models.TextChoices):
        PREVENTIVA = "PREVENTIVA", "Preventiva"
        CORRETIVA = "CORRETIVA", "Corretiva"

    class Status(models.TextChoices):
        ABERTA = "ABERTA", "Aberta"
        CONCLUIDA = "CONCLUIDA", "Concluída"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="frota_manutencoes")
    veiculo = models.ForeignKey(FrotaCadastro, on_delete=models.CASCADE, related_name="manutencoes")
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.PREVENTIVA)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ABERTA)
    data_inicio = models.DateField(default=timezone.localdate)
    data_fim = models.DateField(null=True, blank=True)
    oficina = models.CharField(max_length=120, blank=True, default="")
    descricao = models.TextField(blank=True, default="")
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="frota_manutencoes_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Manutenção de veículo"
        verbose_name_plural = "Manutenções de veículo"
        ordering = ["-data_inicio", "-id"]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["veiculo", "status"]),
        ]

    def __str__(self):
        return f"{self.veiculo} • {self.get_tipo_display()} • {self.get_status_display()}"


class FrotaViagem(models.Model):
    class Status(models.TextChoices):
        ABERTA = "ABERTA", "Aberta"
        CONCLUIDA = "CONCLUIDA", "Concluída"
        CANCELADA = "CANCELADA", "Cancelada"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="frota_viagens")
    veiculo = models.ForeignKey(FrotaCadastro, on_delete=models.CASCADE, related_name="viagens")
    motorista = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="frota_viagens",
    )
    destino = models.CharField(max_length=180)
    finalidade = models.TextField(blank=True, default="")
    data_saida = models.DateField(default=timezone.localdate)
    data_retorno = models.DateField(null=True, blank=True)
    km_saida = models.PositiveIntegerField(default=0)
    km_retorno = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ABERTA)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="frota_viagens_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Viagem"
        verbose_name_plural = "Viagens"
        ordering = ["-data_saida", "-id"]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["veiculo", "status"]),
        ]

    def __str__(self):
        return f"{self.veiculo} • {self.destino}"
