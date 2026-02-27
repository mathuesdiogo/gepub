from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class OuvidoriaCadastro(models.Model):
    class Status(models.TextChoices):
        ABERTO = "ABERTO", "Aberto"
        EM_ANALISE = "EM_ANALISE", "Em análise"
        ENCAMINHADO = "ENCAMINHADO", "Encaminhado"
        RESPONDIDO = "RESPONDIDO", "Respondido"
        CONCLUIDO = "CONCLUIDO", "Concluído"
        CANCELADO = "CANCELADO", "Cancelado"

    class Tipo(models.TextChoices):
        RECLAMACAO = "RECLAMACAO", "Reclamação"
        SUGESTAO = "SUGESTAO", "Sugestão"
        ELOGIO = "ELOGIO", "Elogio"
        DENUNCIA = "DENUNCIA", "Denúncia"
        ESIC = "ESIC", "e-SIC"

    class Prioridade(models.TextChoices):
        BAIXA = "BAIXA", "Baixa"
        MEDIA = "MEDIA", "Média"
        ALTA = "ALTA", "Alta"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="ouvidoria_cadastros")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="ouvidoria_cadastros",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="ouvidoria_cadastros",
        null=True,
        blank=True,
    )
    setor = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="ouvidoria_cadastros",
        null=True,
        blank=True,
    )

    protocolo = models.CharField(max_length=40)
    assunto = models.CharField(max_length=180)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.RECLAMACAO)
    prioridade = models.CharField(max_length=10, choices=Prioridade.choices, default=Prioridade.MEDIA)
    descricao = models.TextField(blank=True, default="")
    solicitante_nome = models.CharField(max_length=160, blank=True, default="")
    solicitante_email = models.EmailField(blank=True, default="")
    solicitante_telefone = models.CharField(max_length=40, blank=True, default="")
    prazo_resposta = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ABERTO)
    respondido_em = models.DateTimeField(null=True, blank=True)
    respondido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ouvidoria_chamados_respondidos",
    )
    observacao = models.TextField(blank=True, default="")

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ouvidoria_cadastros_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Chamado de ouvidoria"
        verbose_name_plural = "Chamados de ouvidoria"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "protocolo"], name="uniq_ouvidoria_protocolo_municipio"),
        ]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["protocolo"]),
            models.Index(fields=["assunto"]),
        ]

    def __str__(self) -> str:
        return f"{self.protocolo} - {self.assunto}"


class OuvidoriaTramitacao(models.Model):
    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="ouvidoria_tramitacoes")
    chamado = models.ForeignKey(OuvidoriaCadastro, on_delete=models.CASCADE, related_name="tramitacoes")
    setor_origem = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="ouvidoria_tramitacoes_origem",
        null=True,
        blank=True,
    )
    setor_destino = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="ouvidoria_tramitacoes_destino",
        null=True,
        blank=True,
    )
    despacho = models.TextField(blank=True, default="")
    ciencia = models.BooleanField(default=False)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ouvidoria_tramitacoes_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tramitação de ouvidoria"
        verbose_name_plural = "Tramitações de ouvidoria"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["municipio", "criado_em"]),
            models.Index(fields=["chamado"]),
        ]

    def __str__(self):
        return f"{self.chamado.protocolo} • {self.criado_em:%d/%m/%Y}"


class OuvidoriaResposta(models.Model):
    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="ouvidoria_respostas")
    chamado = models.ForeignKey(OuvidoriaCadastro, on_delete=models.CASCADE, related_name="respostas")
    resposta = models.TextField()
    publico = models.BooleanField(default=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ouvidoria_respostas_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Resposta da ouvidoria"
        verbose_name_plural = "Respostas da ouvidoria"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["municipio", "publico"]),
            models.Index(fields=["chamado", "criado_em"]),
        ]

    def __str__(self):
        return f"{self.chamado.protocolo} • resposta"
