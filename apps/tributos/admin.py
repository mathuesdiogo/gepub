from django.contrib import admin

from .models import TributoLancamento, TributosCadastro


@admin.register(TributosCadastro)
class TributosCadastroAdmin(admin.ModelAdmin):
    list_display = ("municipio", "codigo", "nome", "documento", "inscricao_municipal", "status")
    list_filter = ("municipio", "tipo_pessoa", "status")
    search_fields = ("codigo", "nome", "documento", "inscricao_municipal")


@admin.register(TributoLancamento)
class TributoLancamentoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "contribuinte", "tipo_tributo", "exercicio", "valor_total", "status")
    list_filter = ("municipio", "tipo_tributo", "status", "exercicio")
    search_fields = ("contribuinte__nome", "referencia")
