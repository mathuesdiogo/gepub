from django.contrib import admin
from .models import Profile, UserManagementAudit


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "municipio", "secretaria", "unidade", "setor", "ativo", "bloqueado")
    list_filter = ("role", "ativo", "bloqueado", "municipio", "secretaria", "unidade")
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name")


@admin.register(UserManagementAudit)
class UserManagementAuditAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "actor", "target")
    list_filter = ("action", "created_at")
    search_fields = ("actor__username", "target__username", "details")
