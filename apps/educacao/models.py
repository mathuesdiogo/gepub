from django.db import models


class Turma(models.Model):
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="turmas",
    )

    nome = models.CharField(max_length=120)  # Ex.: 1º Ano A
    ano_letivo = models.PositiveIntegerField(default=2026)
    turno = models.CharField(
        max_length=20,
        choices=[
            ("MANHA", "Manhã"),
            ("TARDE", "Tarde"),
            ("NOITE", "Noite"),
            ("INTEGRAL", "Integral"),
        ],
        default="MANHA",
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Turma"
        verbose_name_plural = "Turmas"
        ordering = ["-ano_letivo", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["unidade", "ano_letivo", "nome"],
                name="uniq_turma_por_unidade_ano_nome",
            )
        ]
        indexes = [
            models.Index(fields=["ano_letivo"]),
            models.Index(fields=["turno"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.nome} ({self.ano_letivo})"
