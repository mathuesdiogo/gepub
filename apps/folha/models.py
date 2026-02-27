from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class FolhaCadastro(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        INATIVO = "INATIVO", "Inativo"

    class TipoEvento(models.TextChoices):
        PROVENTO = "PROVENTO", "Provento"
        DESCONTO = "DESCONTO", "Desconto"

    class Natureza(models.TextChoices):
        FIXO = "FIXO", "Fixo"
        VARIAVEL = "VARIAVEL", "Variável"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="folha_cadastros")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="folha_cadastros",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="folha_cadastros",
        null=True,
        blank=True,
    )
    setor = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="folha_cadastros",
        null=True,
        blank=True,
    )

    codigo = models.CharField(max_length=40)
    nome = models.CharField(max_length=180)
    tipo_evento = models.CharField(max_length=12, choices=TipoEvento.choices, default=TipoEvento.PROVENTO)
    natureza = models.CharField(max_length=10, choices=Natureza.choices, default=Natureza.FIXO)
    valor_referencia = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    formula_calculo = models.TextField(blank=True, default="")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ATIVO)
    observacao = models.TextField(blank=True, default="")

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="folha_cadastros_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Rubrica de folha"
        verbose_name_plural = "Rubricas de folha"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "codigo"], name="uniq_folha_cadastro_municipio_codigo"),
        ]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["codigo"]),
            models.Index(fields=["nome"]),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} - {self.nome}"


class FolhaCompetencia(models.Model):
    class Status(models.TextChoices):
        ABERTA = "ABERTA", "Aberta"
        PROCESSADA = "PROCESSADA", "Processada"
        FECHADA = "FECHADA", "Fechada"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="folha_competencias")
    competencia = models.CharField(max_length=7, help_text="Formato YYYY-MM")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ABERTA)
    total_colaboradores = models.PositiveIntegerField(default=0)
    total_proventos = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_descontos = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_liquido = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    fechamento_em = models.DateTimeField(null=True, blank=True)
    fechamento_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="folha_competencias_fechadas",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="folha_competencias_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Competência da folha"
        verbose_name_plural = "Competências da folha"
        ordering = ["-competencia"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "competencia"], name="uniq_folha_competencia_municipio"),
        ]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["competencia"]),
        ]

    def __str__(self):
        return f"{self.municipio} • {self.competencia}"


class FolhaLancamento(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        VALIDADO = "VALIDADO", "Validado"
        ENVIADO_FINANCEIRO = "ENVIADO_FINANCEIRO", "Enviado ao financeiro"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="folha_lancamentos")
    competencia = models.ForeignKey(FolhaCompetencia, on_delete=models.CASCADE, related_name="lancamentos")
    servidor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="folha_lancamentos",
    )
    evento = models.ForeignKey(FolhaCadastro, on_delete=models.PROTECT, related_name="lancamentos")
    quantidade = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    valor_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_calculado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    observacao = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDENTE)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="folha_lancamentos_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lançamento de folha"
        verbose_name_plural = "Lançamentos de folha"
        ordering = ["-competencia__competencia", "servidor__first_name"]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["competencia", "servidor"]),
        ]

    def save(self, *args, **kwargs):
        self.valor_calculado = (self.quantidade or 0) * (self.valor_unitario or 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.competencia.competencia} • {self.servidor} • {self.evento.codigo}"


class FolhaIntegracaoFinanceiro(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        ENVIADA = "ENVIADA", "Enviada"
        CONCLUIDA = "CONCLUIDA", "Concluída"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="folha_integracoes_financeiro")
    competencia = models.OneToOneField(FolhaCompetencia, on_delete=models.CASCADE, related_name="integracao_financeiro")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDENTE)
    total_enviado = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    referencia_financeiro = models.CharField(max_length=60, blank=True, default="")
    observacao = models.TextField(blank=True, default="")
    enviado_em = models.DateTimeField(null=True, blank=True)
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="folha_integracoes_enviadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Integração folha-financeiro"
        verbose_name_plural = "Integrações folha-financeiro"
        ordering = ["-competencia__competencia"]
        indexes = [
            models.Index(fields=["municipio", "status"]),
        ]

    def __str__(self):
        return f"{self.competencia.competencia} • {self.get_status_display()}"
