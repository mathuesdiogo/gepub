from django.db import models


class TipoNecessidade(models.Model):
    nome = models.CharField(max_length=120, unique=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Tipo de Necessidade"
        verbose_name_plural = "Tipos de Necessidade"
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["nome"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self) -> str:
        return self.nome


class AlunoNecessidade(models.Model):
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="necessidades",
    )
    tipo = models.ForeignKey(
        "nee.TipoNecessidade",
        on_delete=models.PROTECT,
        related_name="alunos",
    )

    cid = models.CharField("CID (opcional)", max_length=20, blank=True, default="")
    observacao = models.TextField(blank=True, default="")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Necessidade do Aluno"
        verbose_name_plural = "Necessidades do Aluno"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["aluno", "tipo"],
                name="uniq_tipo_por_aluno",
            )
        ]
        indexes = [
            models.Index(fields=["ativo"]),
            models.Index(fields=["cid"]),
        ]

    def __str__(self) -> str:
        return f"{self.aluno} • {self.tipo}"


class ApoioMatricula(models.Model):
    class TipoApoio(models.TextChoices):
        AEE = "AEE", "AEE (Atendimento Educacional Especializado)"
        CUIDADOR = "CUIDADOR", "Cuidador(a)"
        INTERPRETE_LIBRAS = "INTERPRETE_LIBRAS", "Intérprete de Libras"
        PROFESSOR_APOIO = "PROFESSOR_APOIO", "Professor de Apoio"
        TRANSPORTE = "TRANSPORTE", "Transporte Adaptado"
        RECURSO = "RECURSO", "Recurso/Adaptação"
        OUTRO = "OUTRO", "Outro"

    matricula = models.ForeignKey(
        "educacao.Matricula",
        on_delete=models.PROTECT,
        related_name="apoios",
    )

    tipo = models.CharField(max_length=30, choices=TipoApoio.choices)
    descricao = models.CharField(max_length=180, blank=True, default="")
    carga_horaria_semanal = models.PositiveIntegerField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Apoio da Matrícula"
        verbose_name_plural = "Apoios da Matrícula"
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["tipo"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} • {self.matricula}"
