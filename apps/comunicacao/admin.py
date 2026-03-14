from django.contrib import admin

from .models import (
    NotificationChannelConfig,
    NotificationJob,
    NotificationLog,
    NotificationPreference,
    NotificationTenantSettings,
    NotificationTemplate,
    NotificationWebhookEvent,
)


@admin.register(NotificationChannelConfig)
class NotificationChannelConfigAdmin(admin.ModelAdmin):
    list_display = (
        "municipio",
        "secretaria",
        "unidade",
        "channel",
        "provider",
        "is_active",
        "prioridade",
        "last_test_status",
        "last_tested_at",
    )
    list_filter = ("channel", "provider", "is_active", "municipio")
    search_fields = ("municipio__nome", "secretaria__nome", "unidade__nome", "sender_name", "sender_identifier")


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("municipio", "scope", "event_key", "channel", "nome", "is_active", "nee_safe")
    list_filter = ("scope", "channel", "is_active", "nee_safe", "municipio")
    search_fields = ("event_key", "nome", "subject", "body")


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("municipio", "user", "aluno", "nome_contato", "opt_out", "allow_email", "allow_sms", "allow_whatsapp")
    list_filter = ("municipio", "opt_out", "allow_email", "allow_sms", "allow_whatsapp")
    search_fields = ("nome_contato", "email", "telefone", "whatsapp", "user__username", "aluno__nome")


@admin.register(NotificationJob)
class NotificationJobAdmin(admin.ModelAdmin):
    list_display = (
        "municipio",
        "event_key",
        "message_kind",
        "channel",
        "destination",
        "status",
        "priority",
        "attempts",
        "scheduled_at",
    )
    list_filter = ("status", "channel", "priority", "message_kind", "municipio")
    search_fields = ("event_key", "destination", "to_name", "entity_type", "entity_id")


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("job", "status", "attempt", "channel", "provider", "destination", "created_at")
    list_filter = ("status", "channel", "provider")
    search_fields = ("destination", "error_message", "subject")


@admin.register(NotificationTenantSettings)
class NotificationTenantSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "municipio",
        "default_email_provider",
        "default_whatsapp_provider",
        "is_active",
        "onboarding_step",
        "last_validation_status",
    )
    list_filter = ("default_email_provider", "default_whatsapp_provider", "is_active", "last_validation_status")
    search_fields = ("municipio__nome", "sender_email", "sending_domain")


@admin.register(NotificationWebhookEvent)
class NotificationWebhookEventAdmin(admin.ModelAdmin):
    list_display = (
        "provider",
        "event_type",
        "municipio",
        "processing_status",
        "signature_valid",
        "received_at",
    )
    list_filter = ("provider", "processing_status", "signature_valid")
    search_fields = ("external_event_id", "event_type", "destination", "error_message")
