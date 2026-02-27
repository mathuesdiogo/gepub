from django.contrib import admin

from .models import ConectorIntegracao, IntegracaoExecucao


@admin.register(ConectorIntegracao)
class ConectorIntegracaoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "nome", "dominio", "tipo", "ativo")
    list_filter = ("municipio", "dominio", "tipo", "ativo")
    search_fields = ("nome", "endpoint")


@admin.register(IntegracaoExecucao)
class IntegracaoExecucaoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "conector", "direcao", "status", "quantidade_registros", "executado_em")
    list_filter = ("municipio", "status", "direcao")
    search_fields = ("conector__nome", "referencia")
