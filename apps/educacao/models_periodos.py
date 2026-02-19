from django.db import models
from django.conf import settings


# ============================================================
# PERÍODOS LETIVOS (Bimestre / Trimestre / Semestre)
# ============================================================

class PeriodoLetivo(models.Model):
    class Tipo(models.TextChoices):
        BIMESTRE = "BIM", "Bimestre"
        TRIMESTRE = "TRI", "Trimestre"
        SEMESTRE = "SEM", "Semestre"

    ano_letivo = models.IntegerField()
    tipo = models.CharField(
        max_length=3,
        choices=Tipo.choices,
        default=Tipo.BIMESTRE,
    )
    numero = models.PositiveSmallIntegerField()  # 1,2,3,4...
    inicio = models.DateField()
    fim = models.DateField()
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["ano_letivo", "tipo", "numero"]
        unique_together = [("ano_letivo", "tipo", "numero")]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.numero} • {self.ano_letivo}"


# ============================================================
# HORÁRIOS DE TURMA (GRADE SEMANAL)
# ============================================================

class HorarioAula(models.Model):

    class Dia(models.IntegerChoices):
        SEG = 1, "Segunda"
        TER = 2, "Terça"
        QUA = 3, "Quarta"
        QUI = 4, "Quinta"
        SEX = 5, "Sexta"
        SAB = 6, "Sábado"

    turma = models.ForeignKey(
        "educacao.Turma",
        on_delete=models.CASCADE,
        related_name="horarios",
    )

    dia_semana = models.PositiveSmallIntegerField(choices=Dia.choices)

    ordem = models.PositiveSmallIntegerField(
        help_text="Ordem da aula no dia (1ª, 2ª, 3ª...)"
    )

    inicio = models.TimeField()
    fim = models.TimeField()

    componente = models.CharField(
        max_length=120,
        help_text="Disciplina / Componente curricular"
    )

    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="horarios_aula",
    )

    local = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Sala ou local da aula"
    )

    ativo = models.BooleanField(default=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["dia_semana", "ordem", "inicio"]
        unique_together = [("turma", "dia_semana", "ordem")]

    def __str__(self):
        return f"{self.turma} • {self.get_dia_semana_display()} • {self.ordem}ª aula"
