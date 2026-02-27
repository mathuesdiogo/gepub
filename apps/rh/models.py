from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class RhCadastro(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        INATIVO = "INATIVO", "Inativo"

    class Regime(models.TextChoices):
        ESTATUTARIO = "ESTATUTARIO", "Estatutário"
        CLT = "CLT", "CLT"
        COMISSIONADO = "COMISSIONADO", "Comissionado"
        TEMPORARIO = "TEMPORARIO", "Temporário"

    class SituacaoFuncional(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        FERIAS = "FERIAS", "Férias"
        AFASTADO = "AFASTADO", "Afastado"
        CEDIDO = "CEDIDO", "Cedido"
        DESLIGADO = "DESLIGADO", "Desligado"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="rh_cadastros")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="rh_cadastros",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="rh_cadastros",
        null=True,
        blank=True,
    )
    setor = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="rh_cadastros",
        null=True,
        blank=True,
    )

    servidor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_cadastros",
    )
    codigo = models.CharField(max_length=40)
    matricula = models.CharField(max_length=40, blank=True, default="")
    nome = models.CharField(max_length=180)
    cargo = models.CharField(max_length=120, blank=True, default="")
    funcao = models.CharField(max_length=120, blank=True, default="")
    regime = models.CharField(max_length=20, choices=Regime.choices, default=Regime.ESTATUTARIO)
    data_admissao = models.DateField(default=timezone.localdate)
    situacao_funcional = models.CharField(
        max_length=20,
        choices=SituacaoFuncional.choices,
        default=SituacaoFuncional.ATIVO,
    )
    salario_base = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    data_desligamento = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ATIVO)
    observacao = models.TextField(blank=True, default="")

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_cadastros_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Servidor funcional"
        verbose_name_plural = "Servidores funcionais"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "codigo"], name="uniq_rh_cadastro_municipio_codigo"),
            models.UniqueConstraint(
                fields=["municipio", "matricula"],
                condition=~models.Q(matricula=""),
                name="uniq_rh_matricula_municipio",
            ),
        ]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["municipio", "situacao_funcional"]),
            models.Index(fields=["codigo"]),
            models.Index(fields=["matricula"]),
            models.Index(fields=["nome"]),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} - {self.nome}"


class RhMovimentacao(models.Model):
    class Tipo(models.TextChoices):
        ADMISSAO = "ADMISSAO", "Admissão"
        LOTACAO = "LOTACAO", "Mudança de lotação"
        FERIAS = "FERIAS", "Férias"
        AFASTAMENTO = "AFASTAMENTO", "Afastamento"
        PROGRESSAO = "PROGRESSAO", "Progressão"
        DESLIGAMENTO = "DESLIGAMENTO", "Desligamento"

    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        APROVADA = "APROVADA", "Aprovada"
        RECUSADA = "RECUSADA", "Recusada"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="rh_movimentacoes")
    servidor = models.ForeignKey(RhCadastro, on_delete=models.CASCADE, related_name="movimentacoes")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.LOTACAO)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)
    data_inicio = models.DateField(default=timezone.localdate)
    data_fim = models.DateField(null=True, blank=True)
    secretaria_destino = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="rh_movimentacoes_destino",
        null=True,
        blank=True,
    )
    unidade_destino = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="rh_movimentacoes_destino",
        null=True,
        blank=True,
    )
    setor_destino = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="rh_movimentacoes_destino",
        null=True,
        blank=True,
    )
    observacao = models.TextField(blank=True, default="")
    aprovado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_movimentacoes_aprovadas",
    )
    aprovado_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_movimentacoes_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Movimentação funcional"
        verbose_name_plural = "Movimentações funcionais"
        ordering = ["-data_inicio", "-id"]
        indexes = [
            models.Index(fields=["municipio", "status", "tipo"]),
            models.Index(fields=["servidor", "data_inicio"]),
        ]

    def __str__(self):
        return f"{self.servidor.nome} • {self.get_tipo_display()} • {self.data_inicio}"


class RhDocumento(models.Model):
    class Tipo(models.TextChoices):
        PORTARIA = "PORTARIA", "Portaria"
        TERMO = "TERMO", "Termo"
        ATO = "ATO", "Ato"
        NOMEACAO = "NOMEACAO", "Nomeação"
        OUTRO = "OUTRO", "Outro"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="rh_documentos")
    servidor = models.ForeignKey(RhCadastro, on_delete=models.CASCADE, related_name="documentos")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.PORTARIA)
    numero = models.CharField(max_length=60)
    data_documento = models.DateField(default=timezone.localdate)
    descricao = models.TextField(blank=True, default="")
    arquivo = models.FileField(upload_to="rh/documentos/", blank=True, null=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_documentos_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Documento funcional"
        verbose_name_plural = "Documentos funcionais"
        ordering = ["-data_documento", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "numero"], name="uniq_rh_documento_municipio_numero"),
        ]
        indexes = [
            models.Index(fields=["municipio", "tipo", "data_documento"]),
        ]

    def __str__(self):
        return f"{self.numero} • {self.servidor.nome}"
