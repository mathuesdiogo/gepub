from __future__ import annotations

import hashlib
import json
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


def _hash_payload(payload: dict) -> str:
    raw = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


class AvaliacaoProva(models.Model):
    class Tipo(models.TextChoices):
        OBJETIVA = "OBJETIVA", "Objetiva"
        DISCURSIVA = "DISCURSIVA", "Discursiva"
        MISTA = "MISTA", "Mista"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="avaliacoes_provas")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="avaliacoes_provas",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="avaliacoes_provas",
        null=True,
        blank=True,
    )
    setor = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="avaliacoes_provas",
        null=True,
        blank=True,
    )

    turma = models.ForeignKey("educacao.Turma", on_delete=models.PROTECT, related_name="avaliacoes_provas")
    avaliacao_diario = models.ForeignKey(
        "educacao.Avaliacao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="provas_modulo",
    )

    titulo = models.CharField(max_length=180)
    disciplina = models.CharField(max_length=120, blank=True, default="")
    data_aplicacao = models.DateField(default=timezone.localdate)
    peso = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("1.00"))
    nota_maxima = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("10.00"))
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.OBJETIVA)
    opcoes = models.PositiveSmallIntegerField(default=5)
    qtd_questoes = models.PositiveIntegerField(default=10)
    tem_versoes = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="avaliacoes_provas_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Avaliação (Prova)"
        verbose_name_plural = "Avaliações (Provas)"
        ordering = ["-data_aplicacao", "-id"]
        indexes = [
            models.Index(fields=["municipio", "data_aplicacao"]),
            models.Index(fields=["turma", "data_aplicacao"]),
            models.Index(fields=["tipo", "ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.turma} • {self.titulo}"


class QuestaoProva(models.Model):
    class Tipo(models.TextChoices):
        OBJETIVA = "OBJETIVA", "Objetiva"
        DISCURSIVA = "DISCURSIVA", "Discursiva"

    avaliacao = models.ForeignKey(AvaliacaoProva, on_delete=models.CASCADE, related_name="questoes")
    numero = models.PositiveIntegerField()
    enunciado = models.TextField()
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.OBJETIVA)
    alternativas = models.JSONField(default=dict, blank=True)
    peso = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("1.00"))
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Questão da prova"
        verbose_name_plural = "Questões da prova"
        ordering = ["numero", "id"]
        constraints = [
            models.UniqueConstraint(fields=["avaliacao", "numero"], name="uniq_avaliacao_questao_numero"),
        ]

    def __str__(self) -> str:
        return f"{self.avaliacao.titulo} • Q{self.numero}"


class GabaritoProva(models.Model):
    class Versao(models.TextChoices):
        A = "A", "Versão A"
        B = "B", "Versão B"
        C = "C", "Versão C"

    avaliacao = models.ForeignKey(AvaliacaoProva, on_delete=models.CASCADE, related_name="gabaritos")
    versao = models.CharField(max_length=1, choices=Versao.choices, default=Versao.A)
    respostas = models.JSONField(default=dict, blank=True)
    chave_hash = models.CharField(max_length=64, blank=True, default="", db_index=True)

    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gabaritos_provas_atualizados",
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Gabarito"
        verbose_name_plural = "Gabaritos"
        constraints = [
            models.UniqueConstraint(fields=["avaliacao", "versao"], name="uniq_gabarito_avaliacao_versao"),
        ]
        ordering = ["avaliacao_id", "versao"]

    def _payload(self) -> dict:
        return {
            "avaliacao": self.avaliacao_id,
            "versao": self.versao,
            "respostas": self.respostas or {},
        }

    def hash_atual(self) -> str:
        return _hash_payload(self._payload())

    def integridade_ok(self) -> bool:
        if not self.chave_hash:
            return False
        return self.chave_hash == self.hash_atual()

    def save(self, *args, **kwargs):
        self.chave_hash = self.hash_atual()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.avaliacao.titulo} • {self.get_versao_display()}"


class AplicacaoAvaliacao(models.Model):
    class Status(models.TextChoices):
        GERADA = "GERADA", "Gerada"
        ENTREGUE = "ENTREGUE", "Entregue"
        CORRIGIDA = "CORRIGIDA", "Corrigida"

    avaliacao = models.ForeignKey(AvaliacaoProva, on_delete=models.CASCADE, related_name="aplicacoes")
    aluno = models.ForeignKey("educacao.Aluno", on_delete=models.PROTECT, related_name="aplicacoes_provas")
    matricula = models.ForeignKey(
        "educacao.Matricula",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="aplicacoes_provas",
    )
    nota_diario = models.ForeignKey(
        "educacao.Nota",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="aplicacoes_provas",
    )
    versao = models.CharField(max_length=1, default=GabaritoProva.Versao.A)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.GERADA)
    nota = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    percentual = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    corrigido_em = models.DateTimeField(null=True, blank=True)
    corrigido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="aplicacoes_provas_corrigidas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Aplicação da avaliação"
        verbose_name_plural = "Aplicações da avaliação"
        ordering = ["avaliacao_id", "aluno__nome"]
        constraints = [
            models.UniqueConstraint(fields=["avaliacao", "aluno"], name="uniq_aplicacao_avaliacao_aluno"),
        ]
        indexes = [
            models.Index(fields=["avaliacao", "status"]),
            models.Index(fields=["aluno", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.avaliacao.titulo} • {self.aluno}"


class FolhaResposta(models.Model):
    aplicacao = models.OneToOneField(AplicacaoAvaliacao, on_delete=models.CASCADE, related_name="folha")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    versao = models.CharField(max_length=1, default=GabaritoProva.Versao.A)
    respostas_marcadas = models.JSONField(default=dict, blank=True)
    imagem_original = models.FileField(upload_to="avaliacoes/respostas/%Y/%m/", blank=True, null=True)
    confianca_omr = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    hash_assinado = models.CharField(max_length=64, blank=True, default="", db_index=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Folha de resposta"
        verbose_name_plural = "Folhas de resposta"
        ordering = ["-atualizado_em", "-id"]

    def _payload(self) -> dict:
        return {
            "token": str(self.token),
            "aplicacao": self.aplicacao_id,
            "versao": self.versao,
            "respostas": self.respostas_marcadas or {},
        }

    def hash_atual(self) -> str:
        return _hash_payload(self._payload())

    def integridade_ok(self) -> bool:
        if not self.hash_assinado:
            return False
        return self.hash_assinado == self.hash_atual()

    def save(self, *args, **kwargs):
        self.hash_assinado = self.hash_atual()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.aplicacao} • {self.token}"
