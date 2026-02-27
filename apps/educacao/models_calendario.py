from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class CalendarioEducacionalEvento(models.Model):
    class Tipo(models.TextChoices):
        LETIVO = "LETIVO", "Dia letivo"
        FACULTATIVO = "FACULTATIVO", "Ponto facultativo"
        FERIADO = "FERIADO", "Feriado"
        COMEMORATIVA = "COMEMORATIVA", "Data comemorativa"
        BIMESTRE_INICIO = "BIMESTRE_INICIO", "Início de bimestre"
        BIMESTRE_FIM = "BIMESTRE_FIM", "Fim de bimestre"
        PLANEJAMENTO = "PLANEJAMENTO", "Planejamento pedagógico"
        RECESSO = "RECESSO", "Recesso/Férias"
        PEDAGOGICO = "PEDAGOGICO", "Parada pedagógica"
        OUTRO = "OUTRO", "Outro"

    ano_letivo = models.PositiveIntegerField(db_index=True)
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="eventos_calendario_educacao",
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="eventos_calendario_educacao",
    )

    titulo = models.CharField(max_length=160)
    descricao = models.TextField(blank=True, default="")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.OUTRO, db_index=True)

    data_inicio = models.DateField(db_index=True)
    data_fim = models.DateField(blank=True, null=True, db_index=True)
    dia_letivo = models.BooleanField(default=False)
    cor_hex = models.CharField(max_length=7, blank=True, default="")
    ativo = models.BooleanField(default=True)

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eventos_calendario_educacao_criados",
    )
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eventos_calendario_educacao_atualizados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Evento do calendário educacional"
        verbose_name_plural = "Eventos do calendário educacional"
        ordering = ["data_inicio", "titulo", "id"]
        indexes = [
            models.Index(fields=["ano_letivo", "data_inicio"]),
            models.Index(fields=["secretaria", "unidade"]),
            models.Index(fields=["tipo", "ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.titulo} • {self.data_inicio:%d/%m/%Y}"

    def clean(self):
        super().clean()

        if self.data_fim and self.data_fim < self.data_inicio:
            raise ValidationError({"data_fim": "A data final não pode ser anterior à data inicial."})

        if self.unidade_id and self.secretaria_id:
            if getattr(self.unidade, "secretaria_id", None) != self.secretaria_id:
                raise ValidationError({"unidade": "A unidade selecionada não pertence à secretaria informada."})

    @staticmethod
    def default_color_for_tipo(tipo: str) -> str:
        return {
            CalendarioEducacionalEvento.Tipo.LETIVO: "#2563eb",
            CalendarioEducacionalEvento.Tipo.FACULTATIVO: "#d97706",
            CalendarioEducacionalEvento.Tipo.FERIADO: "#dc2626",
            CalendarioEducacionalEvento.Tipo.COMEMORATIVA: "#9333ea",
            CalendarioEducacionalEvento.Tipo.BIMESTRE_INICIO: "#16a34a",
            CalendarioEducacionalEvento.Tipo.BIMESTRE_FIM: "#ea580c",
            CalendarioEducacionalEvento.Tipo.PLANEJAMENTO: "#4f46e5",
            CalendarioEducacionalEvento.Tipo.RECESSO: "#0f766e",
            CalendarioEducacionalEvento.Tipo.PEDAGOGICO: "#4f46e5",
            CalendarioEducacionalEvento.Tipo.OUTRO: "#475569",
        }.get(tipo, "#475569")

    @property
    def data_fim_effective(self):
        return self.data_fim or self.data_inicio

    def save(self, *args, **kwargs):
        if not self.data_fim:
            self.data_fim = self.data_inicio
        if not self.cor_hex:
            self.cor_hex = self.default_color_for_tipo(self.tipo)
        self.full_clean()
        super().save(*args, **kwargs)
