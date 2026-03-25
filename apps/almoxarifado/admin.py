from django.contrib import admin

from .models import (
    AlmoxarifadoCadastro,
    AlmoxarifadoMovimento,
    AlmoxarifadoRequisicao,
    AlmoxarifadoLocal,
    ProdutoEstoque,
    EstoqueSaldo,
    MovimentacaoEstoque,
    RequisicaoEstoque,
)


@admin.register(AlmoxarifadoCadastro)
class AlmoxarifadoCadastroAdmin(admin.ModelAdmin):
    list_display = ("municipio", "secretaria", "unidade", "local_estrutural", "codigo", "nome", "saldo_atual", "estoque_minimo", "status")
    list_filter = ("municipio", "secretaria", "unidade", "status")
    search_fields = ("codigo", "nome")


@admin.register(AlmoxarifadoMovimento)
class AlmoxarifadoMovimentoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "item", "tipo", "data_movimento", "quantidade", "valor_unitario")
    list_filter = ("municipio", "tipo")
    search_fields = ("item__codigo", "item__nome", "documento")


@admin.register(AlmoxarifadoRequisicao)
class AlmoxarifadoRequisicaoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "numero", "item", "unidade_solicitante", "local_solicitante", "quantidade", "status", "criado_em")
    list_filter = ("municipio", "status", "secretaria_solicitante", "unidade_solicitante")
    search_fields = ("numero", "item__codigo", "item__nome")


@admin.register(AlmoxarifadoLocal)
class AlmoxarifadoLocalAdmin(admin.ModelAdmin):
    list_display = ("nome", "municipio", "secretaria", "unidade", "local_estrutural", "tipo", "ativo")
    list_filter = ("municipio", "secretaria", "unidade", "ativo", "tipo")
    search_fields = ("nome", "responsavel", "tipo")


@admin.register(ProdutoEstoque)
class ProdutoEstoqueAdmin(admin.ModelAdmin):
    list_display = ("municipio", "codigo_interno", "nome", "categoria", "unidade_medida", "estoque_minimo", "ativo")
    list_filter = ("municipio", "categoria", "ativo", "controla_lote", "controla_validade")
    search_fields = ("codigo_interno", "nome", "sku")


@admin.register(EstoqueSaldo)
class EstoqueSaldoAdmin(admin.ModelAdmin):
    list_display = ("produto", "almoxarifado_local", "quantidade_atual", "quantidade_reservada", "quantidade_disponivel")
    list_filter = ("almoxarifado_local__municipio", "almoxarifado_local")
    search_fields = ("produto__codigo_interno", "produto__nome", "almoxarifado_local__nome")


@admin.register(MovimentacaoEstoque)
class MovimentacaoEstoqueAdmin(admin.ModelAdmin):
    list_display = ("municipio", "produto", "tipo_movimentacao", "almoxarifado_origem", "almoxarifado_destino", "quantidade", "data_movimentacao")
    list_filter = ("municipio", "tipo_movimentacao")
    search_fields = ("produto__codigo_interno", "produto__nome", "documento_referencia", "motivo")


@admin.register(RequisicaoEstoque)
class RequisicaoEstoqueAdmin(admin.ModelAdmin):
    list_display = ("municipio", "numero", "secretaria", "unidade_solicitante", "local_solicitante", "produto", "quantidade", "status")
    list_filter = ("municipio", "secretaria", "status")
    search_fields = ("numero", "produto__codigo_interno", "produto__nome")
