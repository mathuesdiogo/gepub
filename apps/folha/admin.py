from django.contrib import admin

from .models import FolhaCadastro, FolhaCompetencia, FolhaIntegracaoFinanceiro, FolhaLancamento


@admin.register(FolhaCadastro)
class FolhaCadastroAdmin(admin.ModelAdmin):
    list_display = ("municipio", "codigo", "nome", "tipo_evento", "natureza", "status")
    list_filter = ("municipio", "tipo_evento", "natureza", "status")
    search_fields = ("codigo", "nome")


@admin.register(FolhaCompetencia)
class FolhaCompetenciaAdmin(admin.ModelAdmin):
    list_display = ("municipio", "competencia", "status", "total_colaboradores", "total_liquido")
    list_filter = ("municipio", "status")
    search_fields = ("competencia",)


@admin.register(FolhaLancamento)
class FolhaLancamentoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "competencia", "servidor", "evento", "valor_calculado", "status")
    list_filter = ("municipio", "status", "competencia")
    search_fields = ("servidor__username", "evento__codigo", "evento__nome")


@admin.register(FolhaIntegracaoFinanceiro)
class FolhaIntegracaoFinanceiroAdmin(admin.ModelAdmin):
    list_display = ("municipio", "competencia", "status", "total_enviado", "enviado_em")
    list_filter = ("municipio", "status")
    search_fields = ("competencia__competencia", "referencia_financeiro")
