from django.contrib import admin

from .models import (
    AgendaLegislativa,
    Ata,
    CamaraConfig,
    CamaraOuvidoriaManifestacao,
    Comissao,
    ComissaoMembro,
    DocumentoCamara,
    MesaDiretora,
    NoticiaCamara,
    Pauta,
    Proposicao,
    ProposicaoAutor,
    ProposicaoTramitacao,
    Sessao,
    SessaoDocumento,
    TransparenciaCamaraItem,
    Transmissao,
    Vereador,
)


@admin.register(CamaraConfig)
class CamaraConfigAdmin(admin.ModelAdmin):
    list_display = ("municipio", "nome_portal", "status", "updated_at")
    list_filter = ("status", "contexto")
    search_fields = ("municipio__nome", "nome_portal")


@admin.register(Vereador)
class VereadorAdmin(admin.ModelAdmin):
    list_display = ("municipio", "nome_completo", "partido", "status", "mandato_inicio", "mandato_fim")
    list_filter = ("status", "partido")
    search_fields = ("nome_completo", "nome_parlamentar", "partido")


@admin.register(MesaDiretora)
class MesaDiretoraAdmin(admin.ModelAdmin):
    list_display = ("municipio", "vereador", "cargo", "legislatura", "periodo_inicio", "periodo_fim")
    list_filter = ("cargo", "status")
    search_fields = ("vereador__nome_completo", "legislatura")


@admin.register(Comissao)
class ComissaoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "nome", "tipo", "presidente", "status")
    list_filter = ("tipo", "status")
    search_fields = ("nome",)


@admin.register(ComissaoMembro)
class ComissaoMembroAdmin(admin.ModelAdmin):
    list_display = ("municipio", "comissao", "vereador", "papel", "status")
    list_filter = ("papel", "status")
    search_fields = ("comissao__nome", "vereador__nome_completo")


@admin.register(Sessao)
class SessaoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "titulo", "tipo", "numero", "ano", "situacao", "data_hora")
    list_filter = ("tipo", "situacao", "status")
    search_fields = ("titulo", "numero")


@admin.register(SessaoDocumento)
class SessaoDocumentoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "sessao", "tipo", "titulo", "status", "created_at")
    list_filter = ("tipo", "status")
    search_fields = ("titulo", "sessao__titulo")


@admin.register(Proposicao)
class ProposicaoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "tipo", "numero", "ano", "ementa", "situacao", "status")
    list_filter = ("tipo", "status")
    search_fields = ("numero", "ementa")


@admin.register(ProposicaoAutor)
class ProposicaoAutorAdmin(admin.ModelAdmin):
    list_display = ("municipio", "proposicao", "vereador", "nome_livre", "papel")
    list_filter = ("papel", "status")
    search_fields = ("proposicao__numero", "vereador__nome_completo", "nome_livre")


@admin.register(ProposicaoTramitacao)
class ProposicaoTramitacaoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "proposicao", "etapa", "data_evento", "situacao", "status")
    list_filter = ("status",)
    search_fields = ("proposicao__numero", "etapa", "situacao")


@admin.register(Ata)
class AtaAdmin(admin.ModelAdmin):
    list_display = ("municipio", "numero", "ano", "titulo", "data_documento", "status")
    list_filter = ("status", "ano")
    search_fields = ("numero", "titulo")


@admin.register(Pauta)
class PautaAdmin(admin.ModelAdmin):
    list_display = ("municipio", "numero", "ano", "titulo", "data_documento", "status")
    list_filter = ("status", "ano")
    search_fields = ("numero", "titulo")


@admin.register(NoticiaCamara)
class NoticiaCamaraAdmin(admin.ModelAdmin):
    list_display = ("municipio", "titulo", "categoria", "status", "published_at")
    list_filter = ("categoria", "status")
    search_fields = ("titulo", "resumo")


@admin.register(AgendaLegislativa)
class AgendaLegislativaAdmin(admin.ModelAdmin):
    list_display = ("municipio", "titulo", "tipo", "inicio", "fim", "status")
    list_filter = ("tipo", "status")
    search_fields = ("titulo", "descricao")


@admin.register(Transmissao)
class TransmissaoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "titulo", "status_transmissao", "inicio_previsto", "destaque_home", "status")
    list_filter = ("status_transmissao", "status")
    search_fields = ("titulo",)


@admin.register(TransparenciaCamaraItem)
class TransparenciaCamaraItemAdmin(admin.ModelAdmin):
    list_display = ("municipio", "titulo", "categoria", "formato", "competencia", "status")
    list_filter = ("categoria", "formato", "status")
    search_fields = ("titulo", "descricao")


@admin.register(DocumentoCamara)
class DocumentoCamaraAdmin(admin.ModelAdmin):
    list_display = ("municipio", "titulo", "categoria", "data_documento", "formato", "status")
    list_filter = ("categoria", "formato", "status")
    search_fields = ("titulo", "descricao")


@admin.register(CamaraOuvidoriaManifestacao)
class CamaraOuvidoriaManifestacaoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "protocolo", "tipo", "assunto", "status_atendimento", "status")
    list_filter = ("tipo", "status_atendimento", "status")
    search_fields = ("protocolo", "assunto", "solicitante_nome")
