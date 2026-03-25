from django.contrib import admin

from .models import (
    PatrimonioCadastro,
    PatrimonioInventario,
    PatrimonioMovimentacao,
    BemPatrimonial,
    MovimentacaoPatrimonial,
    InventarioPatrimonial,
    InventarioItem,
)


@admin.register(PatrimonioCadastro)
class PatrimonioCadastroAdmin(admin.ModelAdmin):
    list_display = ("municipio", "secretaria", "unidade", "local_estrutural", "codigo", "tombo", "nome", "categoria", "situacao", "status")
    list_filter = ("municipio", "secretaria", "unidade", "categoria", "situacao", "status")
    search_fields = ("codigo", "tombo", "nome")


@admin.register(PatrimonioMovimentacao)
class PatrimonioMovimentacaoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "bem", "tipo", "unidade_origem", "unidade_destino", "local_origem", "local_destino", "data_movimento")
    list_filter = ("municipio", "tipo")
    search_fields = ("bem__codigo", "bem__nome", "observacao")


@admin.register(PatrimonioInventario)
class PatrimonioInventarioAdmin(admin.ModelAdmin):
    list_display = ("municipio", "codigo", "secretaria", "unidade", "local_estrutural", "status", "total_bens", "total_bens_ativos", "concluido_em")
    list_filter = ("municipio", "secretaria", "unidade", "status")
    search_fields = ("codigo", "referencia")


@admin.register(BemPatrimonial)
class BemPatrimonialAdmin(admin.ModelAdmin):
    list_display = (
        "municipio",
        "numero_tombamento",
        "descricao",
        "secretaria",
        "unidade",
        "local_estrutural",
        "situacao",
        "ativo",
    )
    list_filter = ("municipio", "secretaria", "unidade", "situacao", "estado_conservacao", "ativo")
    search_fields = ("numero_tombamento", "descricao", "numero_serie", "categoria")


@admin.register(MovimentacaoPatrimonial)
class MovimentacaoPatrimonialAdmin(admin.ModelAdmin):
    list_display = (
        "bem",
        "tipo_movimentacao",
        "secretaria_origem",
        "secretaria_destino",
        "unidade_origem",
        "unidade_destino",
        "data_movimentacao",
    )
    list_filter = ("tipo_movimentacao", "secretaria_origem", "secretaria_destino")
    search_fields = ("bem__numero_tombamento", "bem__descricao", "documento_referencia", "motivo")


class InventarioItemInline(admin.TabularInline):
    model = InventarioItem
    extra = 0


@admin.register(InventarioPatrimonial)
class InventarioPatrimonialAdmin(admin.ModelAdmin):
    list_display = ("nome", "municipio", "secretaria", "unidade", "status", "data_abertura", "data_fechamento")
    list_filter = ("municipio", "secretaria", "unidade", "status")
    search_fields = ("nome",)
    inlines = [InventarioItemInline]


@admin.register(InventarioItem)
class InventarioItemAdmin(admin.ModelAdmin):
    list_display = ("inventario", "bem", "status_conferencia", "localizacao_encontrada")
    list_filter = ("status_conferencia",)
    search_fields = ("inventario__nome", "bem__numero_tombamento", "bem__descricao", "localizacao_encontrada")
