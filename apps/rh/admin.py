from django.contrib import admin

from .models import (
    RhCadastro,
    RhDocumento,
    RhMovimentacao,
    RhPdpNecessidade,
    RhPdpPlano,
    RhRemanejamentoEdital,
    RhRemanejamentoInscricao,
    RhRemanejamentoRecurso,
    RhSubstituicaoServidor,
)


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


@admin.register(RhRemanejamentoEdital)
class RhRemanejamentoEditalAdmin(admin.ModelAdmin):
    list_display = ("municipio", "numero", "titulo", "tipo_servidor", "status", "inscricao_inicio", "inscricao_fim")
    list_filter = ("municipio", "tipo_servidor", "status")
    search_fields = ("numero", "titulo")


@admin.register(RhRemanejamentoInscricao)
class RhRemanejamentoInscricaoAdmin(admin.ModelAdmin):
    list_display = ("edital", "servidor", "status", "protocolo", "criado_em")
    list_filter = ("status", "edital__municipio")
    search_fields = ("servidor__nome", "protocolo", "edital__numero")
    filter_horizontal = ("unidades_interesse",)


@admin.register(RhRemanejamentoRecurso)
class RhRemanejamentoRecursoAdmin(admin.ModelAdmin):
    list_display = ("inscricao", "status", "criado_em", "respondido_em")
    list_filter = ("status", "inscricao__edital__municipio")
    search_fields = ("inscricao__servidor__nome", "texto", "resposta")


@admin.register(RhSubstituicaoServidor)
class RhSubstituicaoServidorAdmin(admin.ModelAdmin):
    list_display = ("municipio", "substituido", "substituto", "data_inicio", "data_fim", "status")
    list_filter = ("municipio", "status")
    search_fields = ("substituido__nome", "substituto__nome", "motivo")
    filter_horizontal = ("setores_liberados",)


@admin.register(RhPdpPlano)
class RhPdpPlanoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "ano", "titulo", "status", "aprovado_em", "enviado_sipec_em")
    list_filter = ("municipio", "status", "ano")
    search_fields = ("titulo",)


@admin.register(RhPdpNecessidade)
class RhPdpNecessidadeAdmin(admin.ModelAdmin):
    list_display = ("plano", "tipo_submissao", "area_estrategica", "status", "servidor", "criado_em")
    list_filter = ("status", "tipo_submissao", "municipio", "plano__ano")
    search_fields = ("titulo_acao", "necessidade_a_ser_atendida", "area_estrategica", "area_tematica")
