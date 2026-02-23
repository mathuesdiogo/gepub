from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class TipoNecessidade(models.Model):
    nome = models.CharField(max_length=140, unique=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Tipo de Necessidade"
        verbose_name_plural = "Tipos de Necessidade"
        ordering = ["nome"]
        indexes = [models.Index(fields=["ativo"]), models.Index(fields=["nome"])]

    def __str__(self) -> str:
        return self.nome


class ApoioMatricula(models.Model):
    # Mantém compatibilidade com migração inicial (campos existentes)
    matricula = models.ForeignKey("educacao.Matricula", on_delete=models.PROTECT, related_name="apoios")
    descricao = models.CharField(max_length=200)
    carga_horaria = models.PositiveSmallIntegerField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    # Campos premium (não quebram): tipo/obs/data
    class TipoApoio(models.TextChoices):
        AEE = "AEE", "AEE (Atendimento Educacional Especializado)"
        CUIDADOR = "CUIDADOR", "Cuidador(a)"
        INTERPRETE_LIBRAS = "INTERPRETE_LIBRAS", "Intérprete de Libras"
        PROFESSOR_APOIO = "PROFESSOR_APOIO", "Professor de Apoio"
        TRANSPORTE = "TRANSPORTE", "Transporte Adaptado"
        RECURSO = "RECURSO", "Recurso/Adaptação"
        OUTRO = "OUTRO", "Outro"

    tipo = models.CharField(max_length=30, choices=TipoApoio.choices, default=TipoApoio.OUTRO)
    observacao = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Apoio da Matrícula"
        verbose_name_plural = "Apoios da Matrícula"
        ordering = ["-criado_em", "-id"]
        indexes = [models.Index(fields=["tipo"]), models.Index(fields=["ativo"])]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} — {self.matricula}"


class AlunoNecessidade(models.Model):
    aluno = models.ForeignKey("educacao.Aluno", on_delete=models.PROTECT, related_name="necessidades")
    tipo = models.ForeignKey(TipoNecessidade, on_delete=models.PROTECT, related_name="alunos")
    cid = models.CharField("CID (opcional)", max_length=20, blank=True, default="")
    observacao = models.TextField(blank=True, default="")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Necessidade do Aluno"
        verbose_name_plural = "Necessidades do Aluno"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["ativo"]),
            models.Index(fields=["cid"]),
            models.Index(fields=["aluno"]),
            models.Index(fields=["tipo"]),
        ]

    def __str__(self) -> str:
        return f"{self.aluno} — {self.tipo}"


class LaudoNEE(models.Model):
    aluno = models.ForeignKey("educacao.Aluno", on_delete=models.PROTECT, related_name="laudos_nee")
    numero = models.CharField(max_length=80, blank=True, default="")
    data_emissao = models.DateField(default=timezone.localdate)
    validade = models.DateField(null=True, blank=True)
    profissional = models.CharField(max_length=180, blank=True, default="")
    documento = models.FileField(upload_to="nee/laudos/", blank=True, null=True)
    texto = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Laudo NEE"
        verbose_name_plural = "Laudos NEE"
        ordering = ["-data_emissao", "-id"]
        indexes = [models.Index(fields=["data_emissao"]), models.Index(fields=["aluno"])]

    def __str__(self) -> str:
        return f"Laudo — {self.aluno}"


class RecursoNEE(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        EM_AVALIACAO = "EM_AVALIACAO", "Em avaliação"
        INATIVO = "INATIVO", "Inativo"

    aluno = models.ForeignKey("educacao.Aluno", on_delete=models.PROTECT, related_name="recursos_nee")
    nome = models.CharField(max_length=180)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ATIVO)
    observacao = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Recurso NEE"
        verbose_name_plural = "Recursos NEE"
        ordering = ["nome"]
        indexes = [models.Index(fields=["aluno"]), models.Index(fields=["status"])]

    def __str__(self) -> str:
        return f"{self.nome} — {self.aluno}"


class AcompanhamentoNEE(models.Model):
    class TipoEvento(models.TextChoices):
        OBSERVACAO = "OBSERVACAO", "Observação"
        ATENDIMENTO = "ATENDIMENTO", "Atendimento"
        EVOLUCAO = "EVOLUCAO", "Evolução"
        INTERVENCAO = "INTERVENCAO", "Intervenção"
        DOCUMENTO = "DOCUMENTO", "Documento"

    class Visibilidade(models.TextChoices):
        EQUIPE = "EQUIPE", "Equipe (NEE/Saúde)"
        GESTAO = "GESTAO", "Gestão (Secretaria/Unidade)"

    aluno = models.ForeignKey("educacao.Aluno", on_delete=models.PROTECT, related_name="acompanhamentos_nee")
    data = models.DateField(default=timezone.localdate)
    tipo_evento = models.CharField(max_length=20, choices=TipoEvento.choices, default=TipoEvento.OBSERVACAO)
    descricao = models.TextField()
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="acompanhamentos_nee")
    visibilidade = models.CharField(max_length=20, choices=Visibilidade.choices, default=Visibilidade.EQUIPE)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Acompanhamento NEE"
        verbose_name_plural = "Acompanhamentos NEE"
        ordering = ["-data", "-id"]
        indexes = [models.Index(fields=["aluno"]), models.Index(fields=["data"]), models.Index(fields=["tipo_evento"])]

    def __str__(self) -> str:
        return f"{self.get_tipo_evento_display()} — {self.aluno}"
