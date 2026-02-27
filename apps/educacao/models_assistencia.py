from __future__ import annotations

from django.db import models


class CardapioEscolar(models.Model):
    class Turno(models.TextChoices):
        MANHA = "MANHA", "Manhã"
        TARDE = "TARDE", "Tarde"
        NOITE = "NOITE", "Noite"

    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="cardapios_escolares",
    )
    data = models.DateField()
    turno = models.CharField(max_length=20, choices=Turno.choices, default=Turno.MANHA)
    descricao = models.TextField()
    observacao = models.TextField(blank=True, default="")
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["-data", "unidade__nome", "turno"]
        unique_together = [("unidade", "data", "turno")]
        verbose_name = "Cardápio escolar"
        verbose_name_plural = "Cardápios escolares"

    def __str__(self):
        return f"{self.unidade} • {self.data:%d/%m/%Y} • {self.get_turno_display()}"


class RegistroRefeicaoEscolar(models.Model):
    class Turno(models.TextChoices):
        MANHA = "MANHA", "Manhã"
        TARDE = "TARDE", "Tarde"
        NOITE = "NOITE", "Noite"

    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="registros_refeicao_escolar",
    )
    data = models.DateField()
    turno = models.CharField(max_length=20, choices=Turno.choices, default=Turno.MANHA)
    total_servidas = models.PositiveIntegerField(default=0)
    observacao = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-data", "unidade__nome", "turno"]
        verbose_name = "Registro de refeição escolar"
        verbose_name_plural = "Registros de refeição escolar"

    def __str__(self):
        return f"{self.unidade} • {self.data:%d/%m/%Y} • {self.total_servidas} refeições"


class RotaTransporteEscolar(models.Model):
    class Turno(models.TextChoices):
        MANHA = "MANHA", "Manhã"
        TARDE = "TARDE", "Tarde"
        NOITE = "NOITE", "Noite"

    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="rotas_transporte_escolar",
    )
    nome = models.CharField(max_length=120)
    turno = models.CharField(max_length=20, choices=Turno.choices, default=Turno.MANHA)
    veiculo = models.CharField(max_length=120, blank=True, default="")
    motorista = models.CharField(max_length=120, blank=True, default="")
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["unidade__nome", "nome"]
        unique_together = [("unidade", "nome")]
        verbose_name = "Rota de transporte escolar"
        verbose_name_plural = "Rotas de transporte escolar"

    def __str__(self):
        return f"{self.nome} ({self.unidade})"


class RegistroTransporteEscolar(models.Model):
    data = models.DateField()
    rota = models.ForeignKey(
        "educacao.RotaTransporteEscolar",
        on_delete=models.PROTECT,
        related_name="registros",
    )
    total_previsto = models.PositiveIntegerField(default=0)
    total_transportados = models.PositiveIntegerField(default=0)
    observacao = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-data", "rota__nome"]
        verbose_name = "Registro de transporte escolar"
        verbose_name_plural = "Registros de transporte escolar"

    def __str__(self):
        return f"{self.rota} • {self.data:%d/%m/%Y}"
