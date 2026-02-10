from django.conf import settings
from django.db import models


class Turma(models.Model):
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="turmas",
    )

    # ✅ NOVO: vínculo professor ⇄ turma
    professores = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="turmas_ministradas",
        verbose_name="Professores",
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


class Aluno(models.Model):
    nome = models.CharField(max_length=180)
    data_nascimento = models.DateField(null=True, blank=True)
    cpf = models.CharField(max_length=14, blank=True, default="")
    nis = models.CharField(max_length=20, blank=True, default="")
    nome_mae = models.CharField(max_length=180, blank=True, default="")
    nome_pai = models.CharField(max_length=180, blank=True, default="")
    telefone = models.CharField(max_length=40, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    endereco = models.TextField(blank=True, default="")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Aluno"
        verbose_name_plural = "Alunos"
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["nome"]),
            models.Index(fields=["cpf"]),
            models.Index(fields=["nis"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self) -> str:
        return self.nome


class Matricula(models.Model):
    class Situacao(models.TextChoices):
        ATIVA = "ATIVA", "Ativa"
        TRANSFERIDO = "TRANSFERIDO", "Transferido"
        CONCLUIDO = "CONCLUIDO", "Concluído"
        EVADIDO = "EVADIDO", "Evadido"
        CANCELADO = "CANCELADO", "Cancelado"

    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="matriculas",
    )
    turma = models.ForeignKey(
        "educacao.Turma",
        on_delete=models.PROTECT,
        related_name="matriculas",
    )

    data_matricula = models.DateField(null=True, blank=True)
    situacao = models.CharField(max_length=20, choices=Situacao.choices, default=Situacao.ATIVA)
    observacao = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Matrícula"
        verbose_name_plural = "Matrículas"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["aluno", "turma"],
                name="uniq_aluno_por_turma",
            )
        ]
        indexes = [
            models.Index(fields=["situacao"]),
        ]

    def __str__(self) -> str:
        return f"{self.aluno} → {self.turma}"
