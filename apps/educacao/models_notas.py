from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.db import models


class BNCCCodigo(models.Model):
    class Modalidade(models.TextChoices):
        EDUCACAO_INFANTIL = "EDUCACAO_INFANTIL", "Educação Infantil"
        ENSINO_FUNDAMENTAL = "ENSINO_FUNDAMENTAL", "Ensino Fundamental"
        ENSINO_MEDIO = "ENSINO_MEDIO", "Ensino Médio"

    class Etapa(models.TextChoices):
        EDUCACAO_INFANTIL = "EDUCACAO_INFANTIL", "Educação Infantil"
        FUNDAMENTAL_ANOS_INICIAIS = "FUNDAMENTAL_ANOS_INICIAIS", "Fundamental - Anos Iniciais"
        FUNDAMENTAL_ANOS_FINAIS = "FUNDAMENTAL_ANOS_FINAIS", "Fundamental - Anos Finais"
        ENSINO_MEDIO = "ENSINO_MEDIO", "Ensino Médio"

    codigo = models.CharField(max_length=20, unique=True)
    descricao = models.TextField(blank=True, default="")
    modalidade = models.CharField(max_length=24, choices=Modalidade.choices, db_index=True)
    etapa = models.CharField(max_length=36, choices=Etapa.choices, db_index=True)
    grupo_codigo = models.CharField(
        max_length=8,
        blank=True,
        default="",
        help_text="Prefixo etário/faixa (ex.: EI01, EM13).",
    )
    area_codigo = models.CharField(
        max_length=8,
        blank=True,
        default="",
        db_index=True,
        help_text="Código da área/componente no padrão BNCC (ex.: LP, MA, EO, LGG).",
    )
    ano_inicial = models.PositiveSmallIntegerField(null=True, blank=True)
    ano_final = models.PositiveSmallIntegerField(null=True, blank=True)
    fonte_url = models.URLField(
        blank=True,
        default="https://basenacionalcomum.mec.gov.br/images/BNCC_EI_EF_110518_versaofinal_site.pdf",
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["codigo"]
        verbose_name = "Código BNCC"
        verbose_name_plural = "Códigos BNCC"
        indexes = [
            models.Index(fields=["codigo"]),
            models.Index(fields=["modalidade", "etapa"]),
            models.Index(fields=["area_codigo"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self):
        return self.codigo


class ComponenteCurricular(models.Model):
    nome = models.CharField(max_length=120)
    sigla = models.CharField(max_length=20, blank=True, default="")
    modalidade_bncc = models.CharField(
        max_length=24,
        choices=BNCCCodigo.Modalidade.choices,
        blank=True,
        default="",
        db_index=True,
    )
    etapa_bncc = models.CharField(
        max_length=36,
        choices=BNCCCodigo.Etapa.choices,
        blank=True,
        default="",
    )
    area_codigo_bncc = models.CharField(
        max_length=8,
        blank=True,
        default="",
        help_text="Código da área/componente BNCC (ex.: LP, MA, CG, EO, LGG).",
    )
    codigo_bncc_referencia = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Código BNCC principal de referência para o componente.",
    )
    bncc_codigos = models.ManyToManyField(
        "educacao.BNCCCodigo",
        blank=True,
        related_name="componentes_curriculares",
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Componente curricular"
        verbose_name_plural = "Componentes curriculares"
        unique_together = [("nome", "sigla")]
        indexes = [
            models.Index(fields=["modalidade_bncc", "etapa_bncc"]),
            models.Index(fields=["area_codigo_bncc"]),
        ]

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
