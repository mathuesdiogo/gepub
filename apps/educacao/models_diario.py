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

    data = models.DateField(default=timezone.localdate)
    conteudo = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data"]

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
    diario = models.ForeignKey(
        DiarioTurma,
        on_delete=models.CASCADE,
        related_name="avaliacoes",
    )

    titulo = models.CharField(max_length=160)
    peso = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    data = models.DateField(default=timezone.localdate)

    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titulo


class Nota(models.Model):
    avaliacao = models.ForeignKey(
        Avaliacao,
        on_delete=models.CASCADE,
        related_name="notas",
    )

    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.CASCADE,
        related_name="notas",
    )

    valor = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        unique_together = ("avaliacao", "aluno")

    def __str__(self):
        return f"{self.aluno} — {self.valor}"
