from django.contrib import admin

from .models import (
    DespEmpenho,
    DespLiquidacao,
    DespPagamento,
    DespPagamentoResto,
    DespRestosPagar,
    FinanceiroContaBancaria,
    FinanceiroExercicio,
    FinanceiroLogEvento,
    FinanceiroUnidadeGestora,
    OrcCreditoAdicional,
    OrcDotacao,
    OrcFonteRecurso,
    RecConciliacaoItem,
    RecArrecadacao,
    TesExtratoImportacao,
    TesExtratoItem,
)


@admin.register(FinanceiroExercicio)
class FinanceiroExercicioAdmin(admin.ModelAdmin):
    list_display = ("municipio", "ano", "status", "fechamento_mensal_ate")
    list_filter = ("status", "ano", "municipio")
    search_fields = ("municipio__nome", "ano")


@admin.register(FinanceiroUnidadeGestora)
class FinanceiroUnidadeGestoraAdmin(admin.ModelAdmin):
    list_display = ("municipio", "codigo", "nome", "ativo")
    list_filter = ("ativo", "municipio")
    search_fields = ("codigo", "nome")


@admin.register(FinanceiroContaBancaria)
class FinanceiroContaBancariaAdmin(admin.ModelAdmin):
    list_display = ("municipio", "unidade_gestora", "banco_nome", "agencia", "conta", "saldo_atual", "ativo")
    list_filter = ("ativo", "tipo_conta", "municipio")
    search_fields = ("banco_nome", "agencia", "conta")


@admin.register(OrcFonteRecurso)
class OrcFonteRecursoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "codigo", "nome", "ativo")
    list_filter = ("ativo", "municipio")
    search_fields = ("codigo", "nome")


@admin.register(OrcDotacao)
class OrcDotacaoAdmin(admin.ModelAdmin):
    list_display = (
        "municipio",
        "exercicio",
        "unidade_gestora",
        "programa_codigo",
        "acao_codigo",
        "elemento_despesa",
        "valor_atualizado",
        "valor_empenhado",
        "valor_pago",
    )
    list_filter = ("exercicio", "municipio", "ativo")
    search_fields = ("programa_codigo", "programa_nome", "acao_codigo", "acao_nome", "elemento_despesa")


@admin.register(OrcCreditoAdicional)
class OrcCreditoAdicionalAdmin(admin.ModelAdmin):
    list_display = ("municipio", "exercicio", "tipo", "numero_ato", "data_ato", "valor", "dotacao")
    list_filter = ("tipo", "exercicio", "municipio", "data_ato")
    search_fields = ("numero_ato", "origem_recurso", "dotacao__programa_codigo", "dotacao__acao_codigo")


class DespLiquidacaoInline(admin.TabularInline):
    model = DespLiquidacao
    extra = 0


@admin.register(DespEmpenho)
class DespEmpenhoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "exercicio", "numero", "fornecedor_nome", "valor_empenhado", "valor_liquidado", "valor_pago", "status")
    list_filter = ("status", "tipo", "exercicio", "municipio")
    search_fields = ("numero", "fornecedor_nome", "fornecedor_documento")
    inlines = [DespLiquidacaoInline]


@admin.register(DespLiquidacao)
class DespLiquidacaoAdmin(admin.ModelAdmin):
    list_display = ("empenho", "numero", "data_liquidacao", "valor_liquidado")
    list_filter = ("data_liquidacao",)
    search_fields = ("numero", "empenho__numero", "documento_fiscal")


@admin.register(DespPagamento)
class DespPagamentoAdmin(admin.ModelAdmin):
    list_display = ("liquidacao", "data_pagamento", "valor_pago", "status", "conta_bancaria")
    list_filter = ("status", "data_pagamento")
    search_fields = ("ordem_pagamento", "liquidacao__numero", "liquidacao__empenho__numero")


@admin.register(DespRestosPagar)
class DespRestosPagarAdmin(admin.ModelAdmin):
    list_display = (
        "municipio",
        "numero_inscricao",
        "data_inscricao",
        "empenho",
        "tipo",
        "valor_inscrito",
        "valor_pago",
        "status",
    )
    list_filter = ("status", "tipo", "exercicio_inscricao", "municipio")
    search_fields = ("numero_inscricao", "empenho__numero", "empenho__fornecedor_nome")


@admin.register(DespPagamentoResto)
class DespPagamentoRestoAdmin(admin.ModelAdmin):
    list_display = ("resto", "data_pagamento", "valor", "status", "conta_bancaria")
    list_filter = ("status", "data_pagamento")
    search_fields = ("ordem_pagamento", "resto__numero_inscricao", "resto__empenho__numero")


@admin.register(RecArrecadacao)
class RecArrecadacaoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "exercicio", "rubrica_codigo", "rubrica_nome", "valor", "data_arrecadacao")
    list_filter = ("exercicio", "municipio", "data_arrecadacao")
    search_fields = ("rubrica_codigo", "rubrica_nome", "origem")


@admin.register(TesExtratoImportacao)
class TesExtratoImportacaoAdmin(admin.ModelAdmin):
    list_display = (
        "municipio",
        "exercicio",
        "conta_bancaria",
        "formato",
        "arquivo_nome",
        "total_itens",
        "total_creditos",
        "total_debitos",
        "status",
        "criado_em",
    )
    list_filter = ("status", "formato", "municipio", "exercicio")
    search_fields = ("arquivo_nome", "conta_bancaria__banco_nome", "conta_bancaria__conta")


@admin.register(TesExtratoItem)
class TesExtratoItemAdmin(admin.ModelAdmin):
    list_display = ("importacao", "data_movimento", "documento", "historico", "valor")
    list_filter = ("importacao__municipio", "data_movimento")
    search_fields = ("documento", "historico", "identificador_externo")


@admin.register(RecConciliacaoItem)
class RecConciliacaoItemAdmin(admin.ModelAdmin):
    list_display = ("municipio", "extrato_item", "referencia_tipo", "receita", "desp_pagamento", "desp_pagamento_resto", "conciliado_em")
    list_filter = ("referencia_tipo", "municipio", "conciliado_em")
    search_fields = ("extrato_item__documento", "extrato_item__historico")


@admin.register(FinanceiroLogEvento)
class FinanceiroLogEventoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "evento", "entidade", "entidade_id", "usuario", "criado_em")
    list_filter = ("evento", "entidade", "municipio")
    search_fields = ("evento", "entidade", "entidade_id", "observacao")
