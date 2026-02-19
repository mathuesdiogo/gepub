from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.db import models


class ComponenteCurricular(models.Model):
    nome = models.CharField(max_length=120)
    sigla = models.CharField(max_length=20, blank=True, default="")
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Componente curricular"
        verbose_name_plural = "Componentes curriculares"
        unique_together = [("nome", "sigla")]

    def __str__(self):
        return self.sigla or self.nome


class AvaliacaoNota(models.Model):
    """
    ✅ Avaliação de NOTAS (para não conflitar com models_diario.Avaliacao)
    Uma avaliação pertence a uma Turma e a um Período, e é vinculada a um componente curricular.
    """
    turma = models.ForeignKey("educacao.Turma", on_delete=models.CASCADE, related_name="avaliacoes_notas")
    periodo = models.ForeignKey("educacao.PeriodoLetivo", on_delete=models.PROTECT, related_name="avaliacoes_notas")
    componente = models.ForeignKey("educacao.ComponenteCurricular", on_delete=models.PROTECT, related_name="avaliacoes_notas")

    titulo = models.CharField(max_length=120)
    data = models.DateField(null=True, blank=True)

    peso = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Peso da avaliação (ex.: 1, 2, 0.5).",
    )

    valor_maximo = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("10.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Nota máxima (ex.: 10, 100).",
    )

    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="avaliacoes_notas_criadas",
    )

    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-criado_em", "titulo"]
        verbose_name = "Avaliação (Notas)"
        verbose_name_plural = "Avaliações (Notas)"

    def __str__(self):
        return f"{self.turma} • {self.periodo} • {self.componente} • {self.titulo}"


class NotaCurricular(models.Model):
    """
    Nota curricular do aluno (via Matrícula) em uma AvaliacaoNota.
    """
    avaliacao = models.ForeignKey("educacao.AvaliacaoNota", on_delete=models.CASCADE, related_name="notas_curriculares")
    matricula = models.ForeignKey("educacao.Matricula", on_delete=models.CASCADE, related_name="notas_curriculares")

    valor = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    observacoes = models.CharField(max_length=240, blank=True, default="")
    criado_em = models.DateTimeField(default=timezone.now, editable=False)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("avaliacao", "matricula")]
        ordering = ["matricula_id"]

    def __str__(self):
        return f"{self.matricula_id} • {self.avaliacao_id} • {self.valor}"
