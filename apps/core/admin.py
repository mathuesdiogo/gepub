from django.contrib import admin

from .models import (
    AlunoArquivo,
    AlunoAviso,
    CamaraMateria,
    CamaraSessao,
    ConcursoEtapa,
    ConcursoPublico,
    DiarioOficialEdicao,
    DocumentoEmitido,
    InstitutionalMethodStep,
    InstitutionalPageConfig,
    InstitutionalServiceCard,
    InstitutionalSlide,
    PortalBanner,
    PortalMunicipalConfig,
    PortalHomeBloco,
    PortalMenuPublico,
    PortalPaginaPublica,
    PortalNoticia,
)


@admin.register(AlunoAviso)
class AlunoAvisoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "ativo", "municipio", "secretaria", "unidade", "turma", "aluno", "criado_em")
    list_filter = ("ativo", "municipio", "secretaria")
    search_fields = ("titulo", "texto")


@admin.register(AlunoArquivo)
class AlunoArquivoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "ativo", "municipio", "secretaria", "unidade", "turma", "aluno", "criado_em")
    list_filter = ("ativo", "municipio", "secretaria")
    search_fields = ("titulo", "descricao")


@admin.register(DocumentoEmitido)
class DocumentoEmitidoAdmin(admin.ModelAdmin):
    list_display = ("tipo", "titulo", "codigo", "gerado_por", "gerado_em", "ativo")
    list_filter = ("tipo", "ativo", "gerado_em")
    search_fields = ("titulo", "tipo", "codigo")
    readonly_fields = ("codigo", "gerado_em")


class InstitutionalSlideInline(admin.TabularInline):
    model = InstitutionalSlide
    extra = 1
    fields = (
        "ordem",
        "ativo",
        "titulo",
        "subtitulo",
        "icone",
        "imagem",
        "cta_label",
        "cta_link",
    )


class InstitutionalMethodStepInline(admin.TabularInline):
    model = InstitutionalMethodStep
    extra = 1
    fields = ("ordem", "ativo", "icone", "titulo", "descricao")


class InstitutionalServiceCardInline(admin.TabularInline):
    model = InstitutionalServiceCard
    extra = 1
    fields = ("ordem", "ativo", "icone", "titulo", "descricao")


@admin.register(InstitutionalPageConfig)
class InstitutionalPageConfigAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo", "atualizado_em")
    list_filter = ("ativo",)
    search_fields = ("nome", "marca_nome")
    inlines = [InstitutionalSlideInline, InstitutionalMethodStepInline, InstitutionalServiceCardInline]

    fieldsets = (
        ("Geral", {"fields": ("nome", "ativo", "marca_nome", "marca_logo")}),
        (
            "Navegação",
            {
                "fields": (
                    "nav_metodo_label",
                    "nav_planos_label",
                    "nav_servicos_label",
                    "nav_simulador_label",
                    "botao_login_label",
                )
            },
        ),
        (
            "Hero",
            {
                "fields": (
                    "hero_kicker",
                    "hero_titulo",
                    "hero_descricao",
                    "hero_cta_primario_label",
                    "hero_cta_primario_link",
                    "hero_cta_secundario_label",
                    "hero_cta_secundario_link",
                )
            },
        ),
        ("Oferta + Simulador", {"fields": ("oferta_tag", "oferta_titulo", "oferta_descricao")}),
        (
            "Método",
            {"fields": ("metodo_kicker", "metodo_titulo", "metodo_cta_label", "metodo_cta_link")},
        ),
        (
            "Planos",
            {
                "fields": (
                    "planos_kicker",
                    "planos_titulo",
                    "planos_descricao",
                    "planos_cta_label",
                    "planos_cta_link",
                )
            },
        ),
        (
            "Serviços",
            {"fields": ("servicos_kicker", "servicos_titulo", "servicos_cta_label", "servicos_cta_link")},
        ),
        ("Rodapé", {"fields": ("rodape_texto",)}),
    )


@admin.register(PortalMunicipalConfig)
class PortalMunicipalConfigAdmin(admin.ModelAdmin):
    list_display = ("municipio", "titulo_portal", "telefone", "email", "atualizado_em")
    search_fields = ("municipio__nome", "titulo_portal", "email")


@admin.register(PortalBanner)
class PortalBannerAdmin(admin.ModelAdmin):
    list_display = ("titulo", "municipio", "ordem", "ativo", "criado_em")
    list_filter = ("ativo", "municipio")
    search_fields = ("titulo", "subtitulo", "municipio__nome")


@admin.register(PortalPaginaPublica)
class PortalPaginaPublicaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "municipio", "slug", "publicado", "ordem")
    list_filter = ("publicado", "municipio", "mostrar_no_menu", "mostrar_no_rodape")
    search_fields = ("titulo", "resumo", "conteudo", "slug", "municipio__nome")


@admin.register(PortalMenuPublico)
class PortalMenuPublicoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "municipio", "posicao", "tipo_destino", "ordem", "ativo")
    list_filter = ("ativo", "posicao", "tipo_destino", "municipio")
    search_fields = ("titulo", "municipio__nome")


@admin.register(PortalHomeBloco)
class PortalHomeBlocoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "municipio", "ordem", "ativo")
    list_filter = ("ativo", "municipio")
    search_fields = ("titulo", "descricao", "municipio__nome")


@admin.register(PortalNoticia)
class PortalNoticiaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "municipio", "categoria", "publicado", "destaque", "publicado_em")
    list_filter = ("publicado", "destaque", "categoria", "municipio")
    search_fields = ("titulo", "resumo", "conteudo", "municipio__nome")
    prepopulated_fields = {"slug": ("titulo",)}


@admin.register(DiarioOficialEdicao)
class DiarioOficialEdicaoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "numero", "data_publicacao", "publicado")
    list_filter = ("publicado", "municipio", "data_publicacao")
    search_fields = ("numero", "resumo", "municipio__nome")


class ConcursoEtapaInline(admin.TabularInline):
    model = ConcursoEtapa
    extra = 1
    fields = ("ordem", "titulo", "data_inicio", "data_fim", "publicado")


@admin.register(ConcursoPublico)
class ConcursoPublicoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "municipio", "tipo", "status", "publicado", "criado_em")
    list_filter = ("publicado", "tipo", "status", "municipio")
    search_fields = ("titulo", "descricao", "municipio__nome")
    inlines = [ConcursoEtapaInline]


@admin.register(CamaraMateria)
class CamaraMateriaAdmin(admin.ModelAdmin):
    list_display = ("municipio", "tipo", "numero", "ano", "status", "publicado", "data_publicacao")
    list_filter = ("publicado", "tipo", "status", "municipio", "ano")
    search_fields = ("ementa", "descricao", "numero", "municipio__nome")


@admin.register(CamaraSessao)
class CamaraSessaoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "titulo", "data_sessao", "publicado")
    list_filter = ("publicado", "municipio", "data_sessao")
    search_fields = ("titulo", "pauta", "municipio__nome")
