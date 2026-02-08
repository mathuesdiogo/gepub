from django.contrib import admin
from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "municipio", "unidade", "ativo")
    list_filter = ("role", "ativo", "municipio")
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name")
