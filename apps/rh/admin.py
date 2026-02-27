from django.contrib import admin

from .models import RhCadastro, RhDocumento, RhMovimentacao


@admin.register(RhCadastro)
class RhCadastroAdmin(admin.ModelAdmin):
    list_display = ("municipio", "matricula", "nome", "cargo", "situacao_funcional", "status")
    list_filter = ("municipio", "situacao_funcional", "status")
    search_fields = ("codigo", "matricula", "nome", "cargo", "funcao")


@admin.register(RhMovimentacao)
class RhMovimentacaoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "servidor", "tipo", "status", "data_inicio", "data_fim")
    list_filter = ("municipio", "tipo", "status")
    search_fields = ("servidor__nome", "observacao")


@admin.register(RhDocumento)
class RhDocumentoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "numero", "tipo", "servidor", "data_documento")
    list_filter = ("municipio", "tipo")
    search_fields = ("numero", "servidor__nome", "descricao")
