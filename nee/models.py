from django.conf import settings
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


class LaudoNEE(models.Model):
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="laudos_nee",
    )
    tipo = models.ForeignKey(
        "nee.TipoNecessidade",
        on_delete=models.PROTECT,
        related_name="laudos",
        null=True,
        blank=True,
    )

    numero = models.CharField("Número do laudo (opcional)", max_length=60, blank=True, default="")
    emissor = models.CharField("Emissor/Profissional", max_length=120, blank=True, default="")
    data_emissao = models.DateField(null=True, blank=True)
    validade = models.DateField("Validade (opcional)", null=True, blank=True)

    arquivo = models.FileField(upload_to="nee/laudos/", blank=True, null=True)
    observacao = models.TextField(blank=True, default="")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Laudo NEE"
        verbose_name_plural = "Laudos NEE"
        ordering = ["-data_emissao", "-id"]
        indexes = [
            models.Index(fields=["ativo"]),
            models.Index(fields=["data_emissao"]),
        ]

    def __str__(self) -> str:
        tipo = f" • {self.tipo}" if self.tipo_id else ""
        return f"Laudo{tipo} • {self.aluno}"


class RecursoNEE(models.Model):
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="recursos_nee",
    )
    nome = models.CharField(max_length=120)
    categoria = models.CharField(max_length=80, blank=True, default="")
    descricao = models.TextField(blank=True, default="")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Recurso/Adaptação"
        verbose_name_plural = "Recursos/Adaptações"
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["ativo"]),
            models.Index(fields=["nome"]),
        ]

    def __str__(self) -> str:
        return f"{self.nome} • {self.aluno}"


class AcompanhamentoNEE(models.Model):
    class Status(models.TextChoices):
        ABERTO = "ABERTO", "Aberto"
        EM_ANDAMENTO = "EM_ANDAMENTO", "Em andamento"
        CONCLUIDO = "CONCLUIDO", "Concluído"

    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="acompanhamentos_nee",
    )
    necessidade = models.ForeignKey(
        "nee.AlunoNecessidade",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acompanhamentos",
    )
    profissional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acompanhamentos_nee",
    )

    data = models.DateField(default=datetime.date.today)
    titulo = models.CharField(max_length=140)
    descricao = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ABERTO)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Acompanhamento NEE"
        verbose_name_plural = "Acompanhamentos NEE"
        ordering = ["-data", "-id"]
        indexes = [
            models.Index(fields=["data"]),
            models.Index(fields=["status"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.titulo} • {self.aluno}"


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
