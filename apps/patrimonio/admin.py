from django.contrib import admin

from .models import PatrimonioCadastro, PatrimonioInventario, PatrimonioMovimentacao


@admin.register(PatrimonioCadastro)
class PatrimonioCadastroAdmin(admin.ModelAdmin):
    list_display = ("municipio", "codigo", "tombo", "nome", "categoria", "situacao", "status")
    list_filter = ("municipio", "categoria", "situacao", "status")
    search_fields = ("codigo", "tombo", "nome")


@admin.register(PatrimonioMovimentacao)
class PatrimonioMovimentacaoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "bem", "tipo", "data_movimento", "unidade_destino")
    list_filter = ("municipio", "tipo")
    search_fields = ("bem__codigo", "bem__nome", "observacao")


@admin.register(PatrimonioInventario)
class PatrimonioInventarioAdmin(admin.ModelAdmin):
    list_display = ("municipio", "codigo", "status", "total_bens", "total_bens_ativos", "concluido_em")
    list_filter = ("municipio", "status")
    search_fields = ("codigo", "referencia")
