from django.contrib import admin
from .models import AccessPreviewLog, Profile, UserManagementAudit


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "role",
        "municipio",
        "secretaria",
        "unidade",
        "setor",
        "local_estrutural",
        "ui_theme",
        "ativo",
        "bloqueado",
    )
    list_filter = ("role", "ui_theme", "ativo", "bloqueado", "municipio", "secretaria", "unidade", "local_estrutural")
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name")


@admin.register(UserManagementAudit)
class UserManagementAuditAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "actor", "target")
    list_filter = ("action", "created_at")
    search_fields = ("actor__username", "target__username", "details")


@admin.register(AccessPreviewLog)
class AccessPreviewLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "preview_type", "actor", "target_user", "target_role", "read_only")
    list_filter = ("action", "preview_type", "read_only", "created_at")
    search_fields = ("actor__username", "target_user__username", "target_role", "notes")
