from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def _current_year() -> int:
    return timezone.localdate().year


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


class JustificativaFaltaPedido(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        DEFERIDO = "DEFERIDO", "Deferido"
        INDEFERIDO = "INDEFERIDO", "Indeferido"

    aula = models.ForeignKey(
        Aula,
        on_delete=models.CASCADE,
        related_name="pedidos_justificativa",
    )
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.CASCADE,
        related_name="pedidos_justificativa_falta",
    )
    motivo = models.TextField()
    anexo = models.FileField(upload_to="educacao/justificativas/%Y/%m/", blank=True, null=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDENTE, db_index=True)
    parecer = models.TextField(blank=True, default="")
    analisado_em = models.DateTimeField(null=True, blank=True)
    analisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="justificativas_falta_analisadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["aula", "aluno"],
                name="uniq_justificativa_falta_aula_aluno",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "criado_em"]),
            models.Index(fields=["aluno", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.aluno} • {self.aula} • {self.get_status_display()}"


class PlanoEnsinoProfessor(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        SUBMETIDO = "SUBMETIDO", "Submetido"

    diario = models.ForeignKey(
        DiarioTurma,
        on_delete=models.CASCADE,
        related_name="planos_ensino",
    )
    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="planos_ensino",
    )
    ano_letivo = models.PositiveIntegerField(default=_current_year, db_index=True)
    titulo = models.CharField(max_length=180, default="Plano de Ensino")
    ementa = models.TextField(blank=True, default="")
    objetivos = models.TextField(blank=True, default="")
    metodologia = models.TextField(blank=True, default="")
    criterios_avaliacao = models.TextField(blank=True, default="")
    cronograma = models.TextField(blank=True, default="")
    referencias = models.TextField(blank=True, default="")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RASCUNHO, db_index=True)
    submetido_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-atualizado_em", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["diario", "professor"],
                name="uniq_plano_ensino_por_diario_professor",
            )
        ]
        indexes = [
            models.Index(fields=["professor", "status"]),
            models.Index(fields=["ano_letivo", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.diario.turma.nome} • {self.ano_letivo} • {self.get_status_display()}"

    def submeter(self):
        self.status = self.Status.SUBMETIDO
        self.submetido_em = timezone.now()

    def cancelar_submissao(self):
        self.status = self.Status.RASCUNHO
        self.submetido_em = None


class MaterialAulaProfessor(models.Model):
    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="materiais_aula",
    )
    diario = models.ForeignKey(
        DiarioTurma,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="materiais",
    )
    aula = models.ForeignKey(
        Aula,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="materiais",
    )
    turma_informatica = models.ForeignKey(
        "educacao.InformaticaTurma",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="materiais_professor",
    )
    aula_informatica = models.ForeignKey(
        "educacao.InformaticaAulaDiario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="materiais_professor",
    )
    titulo = models.CharField(max_length=180)
    descricao = models.TextField(blank=True, default="")
    arquivo = models.FileField(upload_to="educacao/materiais/%Y/%m/", blank=True, null=True)
    link_externo = models.URLField(blank=True, default="")
    publico_alunos = models.BooleanField(default=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-atualizado_em", "-id"]
        indexes = [
            models.Index(fields=["professor", "ativo"]),
            models.Index(fields=["diario", "ativo"]),
            models.Index(fields=["turma_informatica", "ativo"]),
        ]

    def clean(self):
        errors = {}
        if not self.arquivo and not (self.link_externo or "").strip():
            errors["arquivo"] = "Informe um arquivo ou link externo para o material."

        if (self.diario_id or self.aula_id) and (self.turma_informatica_id or self.aula_informatica_id):
            errors["diario"] = "Escolha vínculo regular ou de informática, não ambos no mesmo material."

        if self.aula_id and self.diario_id and self.aula.diario_id != self.diario_id:
            errors["aula"] = "A aula selecionada não pertence ao diário informado."
        if self.aula_id and not self.diario_id:
            self.diario = self.aula.diario

        if self.aula_informatica_id and self.turma_informatica_id and self.aula_informatica.turma_id != self.turma_informatica_id:
            errors["aula_informatica"] = "A aula de informática não pertence à turma informada."
        if self.aula_informatica_id and not self.turma_informatica_id:
            self.turma_informatica = self.aula_informatica.turma

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.titulo} • {self.professor}"
