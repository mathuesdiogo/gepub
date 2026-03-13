from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class NotificationChannelConfig(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "EMAIL", "E-mail"
        SMS = "SMS", "SMS"
        WHATSAPP = "WHATSAPP", "WhatsApp"

    class Provider(models.TextChoices):
        SMTP = "SMTP", "SMTP"
        SENDGRID = "SENDGRID", "SendGrid"
        MAILGUN = "MAILGUN", "Mailgun"
        TWILIO = "TWILIO", "Twilio"
        ZENVIA = "ZENVIA", "Zenvia"
        META = "META", "Meta Cloud API"
        MOCK = "MOCK", "Mock interno"
        OUTRO = "OUTRO", "Outro"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="notification_channels")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="notification_channels",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="notification_channels",
        null=True,
        blank=True,
    )
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.EMAIL)
    provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.MOCK)
    sender_name = models.CharField(max_length=120, blank=True, default="")
    sender_identifier = models.CharField(
        max_length=180,
        blank=True,
        default="",
        help_text="E-mail remetente ou número/identificador do canal.",
    )
    credentials_json = models.JSONField(default=dict, blank=True)
    options_json = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    prioridade = models.PositiveSmallIntegerField(default=10)

    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_channels_updated",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Canal de comunicação"
        verbose_name_plural = "Canais de comunicação"
        ordering = ["municipio__nome", "channel", "prioridade", "id"]
        indexes = [
            models.Index(fields=["municipio", "channel", "is_active"]),
            models.Index(fields=["secretaria", "channel", "is_active"]),
            models.Index(fields=["unidade", "channel", "is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["municipio", "secretaria", "unidade", "channel", "provider"],
                name="uniq_notification_channel_scope",
            )
        ]

    def __str__(self) -> str:
        scope = self.unidade or self.secretaria or self.municipio
        return f"{scope} • {self.get_channel_display()} • {self.get_provider_display()}"


class NotificationTemplate(models.Model):
    class Scope(models.TextChoices):
        MUNICIPIO = "MUNICIPIO", "Município"
        SECRETARIA = "SECRETARIA", "Secretaria"
        UNIDADE = "UNIDADE", "Unidade"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="notification_templates")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="notification_templates",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="notification_templates",
        null=True,
        blank=True,
    )
    scope = models.CharField(max_length=20, choices=Scope.choices, default=Scope.MUNICIPIO)
    event_key = models.CharField(max_length=80, db_index=True)
    channel = models.CharField(
        max_length=20,
        choices=NotificationChannelConfig.Channel.choices,
        default=NotificationChannelConfig.Channel.EMAIL,
    )
    nome = models.CharField(max_length=140)
    subject = models.CharField(max_length=220, blank=True, default="")
    body = models.TextField()
    is_active = models.BooleanField(default=True)
    nee_safe = models.BooleanField(
        default=False,
        help_text="Quando ativo, indica template neutro para comunicações sensíveis.",
    )

    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_templates_updated",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Template de notificação"
        verbose_name_plural = "Templates de notificação"
        ordering = ["event_key", "channel", "nome"]
        indexes = [
            models.Index(fields=["municipio", "event_key", "channel", "is_active"]),
            models.Index(fields=["secretaria", "event_key", "channel", "is_active"]),
            models.Index(fields=["unidade", "event_key", "channel", "is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["municipio", "secretaria", "unidade", "event_key", "channel", "nome"],
                name="uniq_notification_template_scope_event",
            )
        ]

    def __str__(self) -> str:
        return f"{self.event_key} • {self.get_channel_display()} • {self.nome}"


class NotificationPreference(models.Model):
    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="notification_preferences")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
        null=True,
        blank=True,
    )
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.CASCADE,
        related_name="notification_preferences",
        null=True,
        blank=True,
    )
    nome_contato = models.CharField(max_length=140, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    telefone = models.CharField(max_length=40, blank=True, default="")
    whatsapp = models.CharField(max_length=40, blank=True, default="")
    allow_email = models.BooleanField(default=True)
    allow_sms = models.BooleanField(default=True)
    allow_whatsapp = models.BooleanField(default=True)
    opt_out = models.BooleanField(default=False)
    horario_inicio = models.TimeField(null=True, blank=True)
    horario_fim = models.TimeField(null=True, blank=True)
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_preferences_updated",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Preferência de notificação"
        verbose_name_plural = "Preferências de notificação"
        ordering = ["-atualizado_em", "-id"]
        indexes = [
            models.Index(fields=["municipio", "opt_out"]),
            models.Index(fields=["user", "municipio"]),
            models.Index(fields=["aluno", "municipio"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["municipio", "user", "aluno", "email", "telefone", "whatsapp"],
                name="uniq_notification_preference_identity",
            )
        ]

    def __str__(self) -> str:
        if self.user_id:
            return f"{self.user} • Preferências"
        if self.aluno_id:
            return f"{self.aluno} • Preferências"
        return self.nome_contato or self.email or self.whatsapp or f"Preferência #{self.pk}"


class NotificationJob(models.Model):
    class Priority(models.TextChoices):
        URGENTE = "URGENTE", "Urgente"
        ALTA = "ALTA", "Alta"
        NORMAL = "NORMAL", "Normal"
        BAIXA = "BAIXA", "Baixa"

    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        PROCESSANDO = "PROCESSANDO", "Processando"
        ENVIADO = "ENVIADO", "Enviado"
        ENTREGUE = "ENTREGUE", "Entregue"
        FALHA = "FALHA", "Falha"
        CANCELADO = "CANCELADO", "Cancelado"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="notification_jobs")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="notification_jobs",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="notification_jobs",
        null=True,
        blank=True,
    )
    event_key = models.CharField(max_length=80, db_index=True)
    channel = models.CharField(
        max_length=20,
        choices=NotificationChannelConfig.Channel.choices,
        default=NotificationChannelConfig.Channel.EMAIL,
    )
    provider = models.CharField(max_length=20, blank=True, default="")
    to_name = models.CharField(max_length=140, blank=True, default="")
    destination = models.CharField(max_length=180)
    payload_json = models.JSONField(default=dict, blank=True)
    subject_rendered = models.CharField(max_length=220, blank=True, default="")
    body_rendered = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDENTE, db_index=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    fallback_channels = models.JSONField(default=list, blank=True)
    fallback_index = models.PositiveSmallIntegerField(default=0)
    provider_message_id = models.CharField(max_length=120, blank=True, default="")
    error_message = models.TextField(blank=True, default="")

    entity_module = models.CharField(max_length=40, blank=True, default="")
    entity_type = models.CharField(max_length=80, blank=True, default="")
    entity_id = models.CharField(max_length=60, blank=True, default="")

    scheduled_at = models.DateTimeField(default=timezone.now, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_jobs_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Job de notificação"
        verbose_name_plural = "Jobs de notificação"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["municipio", "status", "scheduled_at"]),
            models.Index(fields=["channel", "status", "scheduled_at"]),
            models.Index(fields=["event_key", "created_at"]),
            models.Index(fields=["entity_module", "entity_type", "entity_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_key} • {self.get_channel_display()} • {self.get_status_display()}"


class NotificationLog(models.Model):
    job = models.ForeignKey(NotificationJob, on_delete=models.CASCADE, related_name="logs")
    status = models.CharField(max_length=20, choices=NotificationJob.Status.choices, db_index=True)
    attempt = models.PositiveSmallIntegerField(default=1)
    channel = models.CharField(max_length=20, choices=NotificationChannelConfig.Channel.choices)
    provider = models.CharField(max_length=20, blank=True, default="")
    destination = models.CharField(max_length=180, blank=True, default="")
    subject = models.CharField(max_length=220, blank=True, default="")
    body = models.TextField(blank=True, default="")
    provider_response = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Log de notificação"
        verbose_name_plural = "Logs de notificação"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["channel", "status", "created_at"]),
            models.Index(fields=["provider", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Job #{self.job_id} • {self.get_status_display()} • Tentativa {self.attempt}"
