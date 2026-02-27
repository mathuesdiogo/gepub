from django.contrib import admin

from .models import AlmoxarifadoCadastro, AlmoxarifadoMovimento, AlmoxarifadoRequisicao


@admin.register(AlmoxarifadoCadastro)
class AlmoxarifadoCadastroAdmin(admin.ModelAdmin):
    list_display = ("municipio", "codigo", "nome", "saldo_atual", "estoque_minimo", "status")
    list_filter = ("municipio", "status")
    search_fields = ("codigo", "nome")


@admin.register(AlmoxarifadoMovimento)
class AlmoxarifadoMovimentoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "item", "tipo", "data_movimento", "quantidade", "valor_unitario")
    list_filter = ("municipio", "tipo")
    search_fields = ("item__codigo", "item__nome", "documento")


@admin.register(AlmoxarifadoRequisicao)
class AlmoxarifadoRequisicaoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "numero", "item", "quantidade", "status", "criado_em")
    list_filter = ("municipio", "status")
    search_fields = ("numero", "item__codigo", "item__nome")
