from django.conf import settings
from django.db import models
from django.utils import timezone


class DiarioTurma(models.Model):
    turma = models.ForeignKey(
        "educacao.Turma",
        on_delete=models.CASCADE,
        related_name="diarios",
    )
    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="diarios",
    )
    ano_letivo = models.PositiveIntegerField(default=timezone.now().year)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("turma", "professor", "ano_letivo")
        ordering = ["-ano_letivo"]

    def __str__(self):
        return f"{self.turma} — {self.professor}"


class Aula(models.Model):
    diario = models.ForeignKey(
        DiarioTurma,
        on_delete=models.CASCADE,
        related_name="aulas",
    )
    periodo = models.ForeignKey(
        "educacao.PeriodoLetivo",
        on_delete=models.PROTECT,
        related_name="aulas_diario",
        null=True,
        blank=True,
    )
    componente = models.ForeignKey(
        "educacao.ComponenteCurricular",
        on_delete=models.SET_NULL,
        related_name="aulas_diario",
        null=True,
        blank=True,
    )
    data = models.DateField(default=timezone.localdate)
    bncc_codigos = models.ManyToManyField(
        "educacao.BNCCCodigo",
        blank=True,
        related_name="aulas",
    )
    conteudo = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data"]
        indexes = [
            models.Index(fields=["data"]),
            models.Index(fields=["periodo"]),
            models.Index(fields=["componente"]),
        ]

    def __str__(self):
        return f"{self.diario} — {self.data}"


class Frequencia(models.Model):
    class Status(models.TextChoices):
        PRESENTE = "P", "Presente"
        FALTA = "F", "Falta"
        JUSTIFICADA = "J", "Justificada"

    aula = models.ForeignKey(
        Aula,
        on_delete=models.CASCADE,
        related_name="frequencias",
    )
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.CASCADE,
        related_name="frequencias",
    )
    status = models.CharField(max_length=1, choices=Status.choices, default=Status.PRESENTE)

    class Meta:
        unique_together = ("aula", "aluno")

    def __str__(self):
        return f"{self.aluno} — {self.get_status_display()}"


class Avaliacao(models.Model):
    """
    ✅ MODELO ÚNICO DE AVALIAÇÃO DO APP 'educacao'
    (evita conflito com models_notas.py)
    """
    diario = models.ForeignKey(
        DiarioTurma,
        on_delete=models.CASCADE,
        related_name="avaliacoes",
    )

    # ✅ opcional: vincular em um período (bimestre/trimestre/semestre)
    periodo = models.ForeignKey(
        "educacao.PeriodoLetivo",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="avaliacoes",
    )

    titulo = models.CharField(max_length=160)
    peso = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    nota_maxima = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    data = models.DateField(default=timezone.localdate)

    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data", "-id"]
        indexes = [
            models.Index(fields=["data"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self):
        return self.titulo

class Nota(models.Model):
    """Nota lançada em uma Avaliação (Diário de Classe).

    Mantida exatamente no padrão da migration 0007 (tabela educacao_nota),
    para evitar conflitos com notas curriculares.
    """
    avaliacao = models.ForeignKey("educacao.Avaliacao", on_delete=models.CASCADE, related_name="notas")
    aluno = models.ForeignKey("educacao.Aluno", on_delete=models.CASCADE, related_name="notas")
    valor = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        unique_together = [("avaliacao", "aluno")]
        ordering = ["aluno_id"]

    def __str__(self) -> str:
        return f"{self.aluno_id} • {self.avaliacao_id} • {self.valor}"
