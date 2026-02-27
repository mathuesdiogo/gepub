from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class PontoCadastro(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        INATIVO = "INATIVO", "Inativo"

    class Turno(models.TextChoices):
        MATUTINO = "MATUTINO", "Matutino"
        VESPERTINO = "VESPERTINO", "Vespertino"
        NOTURNO = "NOTURNO", "Noturno"
        INTEGRAL = "INTEGRAL", "Integral"
        PLANTAO = "PLANTAO", "Plantão"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="ponto_cadastros")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="ponto_cadastros",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="ponto_cadastros",
        null=True,
        blank=True,
    )
    setor = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="ponto_cadastros",
        null=True,
        blank=True,
    )

    codigo = models.CharField(max_length=40)
    nome = models.CharField(max_length=180)
    tipo_turno = models.CharField(max_length=20, choices=Turno.choices, default=Turno.MATUTINO)
    hora_entrada = models.TimeField(null=True, blank=True)
    hora_saida = models.TimeField(null=True, blank=True)
    carga_horaria_semanal = models.DecimalField(max_digits=5, decimal_places=2, default=40)
    tolerancia_entrada_min = models.PositiveSmallIntegerField(default=10)
    dias_semana = models.CharField(max_length=80, blank=True, default="SEG,TER,QUA,QUI,SEX")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ATIVO)
    observacao = models.TextField(blank=True, default="")

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ponto_cadastros_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Escala e turno"
        verbose_name_plural = "Escalas e turnos"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "codigo"], name="uniq_ponto_cadastro_municipio_codigo"),
        ]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["codigo"]),
            models.Index(fields=["nome"]),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} - {self.nome}"


class PontoVinculoEscala(models.Model):
    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="ponto_vinculos")
    escala = models.ForeignKey(PontoCadastro, on_delete=models.PROTECT, related_name="vinculos")
    servidor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ponto_vinculos")
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="ponto_vinculos",
        null=True,
        blank=True,
    )
    setor = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="ponto_vinculos",
        null=True,
        blank=True,
    )
    data_inicio = models.DateField(default=timezone.localdate)
    data_fim = models.DateField(null=True, blank=True)
    ativo = models.BooleanField(default=True)
    observacao = models.TextField(blank=True, default="")

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ponto_vinculos_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Vínculo de escala"
        verbose_name_plural = "Vínculos de escala"
        ordering = ["-ativo", "servidor__first_name", "servidor__username"]
        indexes = [
            models.Index(fields=["municipio", "ativo"]),
            models.Index(fields=["data_inicio", "data_fim"]),
        ]

    def __str__(self) -> str:
        return f"{self.servidor} • {self.escala}"


class PontoOcorrencia(models.Model):
    class Tipo(models.TextChoices):
        ATRASO = "ATRASO", "Atraso"
        FALTA = "FALTA", "Falta"
        ABONO = "ABONO", "Abono"
        HORA_EXTRA = "HORA_EXTRA", "Hora extra"
        AJUSTE = "AJUSTE", "Ajuste manual"

    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        APROVADA = "APROVADA", "Aprovada"
        RECUSADA = "RECUSADA", "Recusada"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="ponto_ocorrencias")
    vinculo = models.ForeignKey(
        PontoVinculoEscala,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocorrencias",
    )
    servidor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ponto_ocorrencias")
    data_ocorrencia = models.DateField()
    competencia = models.CharField(max_length=7, help_text="Formato YYYY-MM")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.ATRASO)
    minutos = models.IntegerField(default=0)
    descricao = models.TextField(blank=True, default="")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)

    avaliado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ponto_ocorrencias_avaliadas",
    )
    avaliado_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ponto_ocorrencias_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ocorrência de ponto"
        verbose_name_plural = "Ocorrências de ponto"
        ordering = ["-data_ocorrencia", "-id"]
        indexes = [
            models.Index(fields=["municipio", "competencia", "status"]),
            models.Index(fields=["servidor", "data_ocorrencia"]),
            models.Index(fields=["tipo"]),
        ]

    def __str__(self) -> str:
        return f"{self.servidor} • {self.get_tipo_display()} • {self.data_ocorrencia}"

    def save(self, *args, **kwargs):
        if self.data_ocorrencia and not self.competencia:
            self.competencia = self.data_ocorrencia.strftime("%Y-%m")
        super().save(*args, **kwargs)


class PontoFechamentoCompetencia(models.Model):
    class Status(models.TextChoices):
        ABERTA = "ABERTA", "Aberta"
        FECHADA = "FECHADA", "Fechada"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="ponto_competencias")
    competencia = models.CharField(max_length=7, help_text="Formato YYYY-MM")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ABERTA)

    total_servidores = models.PositiveIntegerField(default=0)
    total_ocorrencias = models.PositiveIntegerField(default=0)
    total_pendentes = models.PositiveIntegerField(default=0)

    observacao = models.TextField(blank=True, default="")
    fechado_em = models.DateTimeField(null=True, blank=True)
    fechado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ponto_competencias_fechadas",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ponto_competencias_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Fechamento de competência"
        verbose_name_plural = "Fechamentos de competência"
        ordering = ["-competencia"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "competencia"], name="uniq_ponto_competencia_municipio"),
        ]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["competencia"]),
        ]

    def __str__(self) -> str:
        return f"{self.municipio} • {self.competencia}"
