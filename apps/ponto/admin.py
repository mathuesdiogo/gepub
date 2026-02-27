from django.contrib import admin

from .models import PontoCadastro, PontoFechamentoCompetencia, PontoOcorrencia, PontoVinculoEscala


@admin.register(PontoCadastro)
class PontoCadastroAdmin(admin.ModelAdmin):
    list_display = ("municipio", "codigo", "nome", "tipo_turno", "status")
    list_filter = ("municipio", "status", "tipo_turno")
    search_fields = ("codigo", "nome")


@admin.register(PontoVinculoEscala)
class PontoVinculoEscalaAdmin(admin.ModelAdmin):
    list_display = ("municipio", "servidor", "escala", "data_inicio", "data_fim", "ativo")
    list_filter = ("municipio", "ativo")
    search_fields = ("servidor__username", "servidor__first_name", "escala__nome", "escala__codigo")


@admin.register(PontoOcorrencia)
class PontoOcorrenciaAdmin(admin.ModelAdmin):
    list_display = ("municipio", "servidor", "data_ocorrencia", "competencia", "tipo", "status")
    list_filter = ("municipio", "status", "tipo", "competencia")
    search_fields = ("servidor__username", "servidor__first_name", "descricao")


@admin.register(PontoFechamentoCompetencia)
class PontoFechamentoCompetenciaAdmin(admin.ModelAdmin):
    list_display = ("municipio", "competencia", "status", "total_servidores", "total_ocorrencias", "total_pendentes")
    list_filter = ("municipio", "status")
    search_fields = ("municipio__nome", "competencia")
