from __future__ import annotations

from django.conf import settings
from django.db import models


class ScheduleConflictSetting(models.Model):
    class ValidationMode(models.TextChoices):
        BLOCK = "BLOCK", "Bloqueio obrigatório"
        WARN = "WARN", "Aviso com permissão especial"
        ALLOW = "ALLOW", "Apenas aviso"

    nome = models.CharField(max_length=80, default="Política padrão de conflitos")
    modo_validacao = models.CharField(
        max_length=10,
        choices=ValidationMode.choices,
        default=ValidationMode.BLOCK,
    )
    permitir_excecao = models.BooleanField(default=True)
    exigir_justificativa_excecao = models.BooleanField(default=True)
    considerar_intervalos_encostados_validos = models.BooleanField(default=True)
    considerar_conflito_entre_modulos = models.BooleanField(default=True)
    validar_importacoes = models.BooleanField(default=True)
    validar_edicao_grade = models.BooleanField(default=True)
    ativar_alerta_visual = models.BooleanField(default=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração de conflito de horários"
        verbose_name_plural = "Configurações de conflito de horários"
        ordering = ["-ativo", "-id"]
        indexes = [
            models.Index(fields=["ativo"]),
            models.Index(fields=["modo_validacao", "ativo"]),
        ]

    @classmethod
    def resolve(cls) -> "ScheduleConflictSetting":
        setting = cls.objects.filter(ativo=True).order_by("-id").first()
        if setting:
            return setting
        return cls()

    @property
    def blocking_mode(self) -> str:
        mode = (self.modo_validacao or self.ValidationMode.BLOCK).upper()
        if mode not in {
            self.ValidationMode.BLOCK,
            self.ValidationMode.WARN,
            self.ValidationMode.ALLOW,
        }:
            return self.ValidationMode.BLOCK
        return mode

    def __str__(self) -> str:
        return f"{self.nome} ({self.get_modo_validacao_display()})"


class ScheduleConflictOverride(models.Model):
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="overrides_conflito_horario",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="overrides_conflito_horario",
    )
    contexto = models.CharField(max_length=80, blank=True, default="")
    modo_aplicado = models.CharField(
        max_length=10,
        choices=ScheduleConflictSetting.ValidationMode.choices,
        default=ScheduleConflictSetting.ValidationMode.BLOCK,
    )
    justificativa = models.TextField()
    ip_origem = models.CharField(max_length=64, blank=True, default="")

    nova_oferta_tipo = models.CharField(max_length=40, blank=True, default="")
    nova_oferta_id = models.PositiveIntegerField(null=True, blank=True)
    nova_oferta_nome = models.CharField(max_length=220, blank=True, default="")

    oferta_conflitante_tipo = models.CharField(max_length=40, blank=True, default="")
    oferta_conflitante_id = models.PositiveIntegerField(null=True, blank=True)
    oferta_conflitante_nome = models.CharField(max_length=220, blank=True, default="")

    unidade_nome = models.CharField(max_length=180, blank=True, default="")
    secretaria_nome = models.CharField(max_length=180, blank=True, default="")
    payload_resumo = models.JSONField(default=dict, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Override de conflito de horário"
        verbose_name_plural = "Overrides de conflito de horário"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["aluno", "criado_em"]),
            models.Index(fields=["usuario", "criado_em"]),
            models.Index(fields=["contexto"]),
            models.Index(fields=["modo_aplicado"]),
        ]

    def __str__(self) -> str:
        return f"{self.aluno} • {self.contexto or 'OVERRIDE'} • {self.criado_em:%d/%m/%Y %H:%M}"
