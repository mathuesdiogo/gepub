from django.db import models
from django.conf import settings


class GradeHorario(models.Model):
    turma = models.OneToOneField("educacao.Turma", on_delete=models.CASCADE, related_name="grade_horario")
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Grade {self.turma.nome} ({self.turma.ano_letivo})"


class AulaHorario(models.Model):
    class Dia(models.TextChoices):
        SEG = "SEG", "Segunda"
        TER = "TER", "Terça"
        QUA = "QUA", "Quarta"
        QUI = "QUI", "Quinta"
        SEX = "SEX", "Sexta"
        SAB = "SAB", "Sábado"

    grade = models.ForeignKey(GradeHorario, on_delete=models.CASCADE, related_name="aulas")
    dia = models.CharField(max_length=3, choices=Dia.choices)
    inicio = models.TimeField()
    fim = models.TimeField()

    disciplina = models.CharField(max_length=120)
    professor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    sala = models.CharField(max_length=60, blank=True, default="")
    observacoes = models.CharField(max_length=180, blank=True, default="")

    class Meta:
        ordering = ["dia", "inicio"]
        unique_together = [("grade", "dia", "inicio", "fim")]

    def __str__(self):
        return f"{self.get_dia_display()} {self.inicio}-{self.fim} • {self.disciplina}"
