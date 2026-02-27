from django.contrib import admin

from .models import (
    AddonCatalogo,
    AssinaturaAddon,
    AssinaturaMunicipio,
    AssinaturaQuotaExtra,
    FaturaMunicipio,
    PlanoMunicipal,
    SolicitacaoUpgrade,
    UsoMunicipio,
)


@admin.register(PlanoMunicipal)
class PlanoMunicipalAdmin(admin.ModelAdmin):
    list_display = ("nome", "codigo", "preco_base_mensal", "limite_secretarias", "limite_usuarios", "limite_alunos", "ativo")
    list_filter = ("codigo", "ativo")
    search_fields = ("nome", "codigo")


@admin.register(AssinaturaMunicipio)
class AssinaturaMunicipioAdmin(admin.ModelAdmin):
    list_display = ("municipio", "plano", "status", "inicio_vigencia", "fim_vigencia", "preco_base_congelado")
    list_filter = ("status", "plano")
    search_fields = ("municipio__nome",)


@admin.register(UsoMunicipio)
class UsoMunicipioAdmin(admin.ModelAdmin):
    list_display = ("municipio", "ano_referencia", "secretarias_ativas", "usuarios_ativos", "alunos_ativos", "atendimentos_ano", "atualizado_em")
    search_fields = ("municipio__nome",)


@admin.register(SolicitacaoUpgrade)
class SolicitacaoUpgradeAdmin(admin.ModelAdmin):
    list_display = ("municipio", "tipo", "quantidade", "valor_mensal_calculado", "status", "solicitado_em", "aprovado_em")
    list_filter = ("tipo", "status")
    search_fields = ("municipio__nome", "observacao")


@admin.register(AssinaturaQuotaExtra)
class AssinaturaQuotaExtraAdmin(admin.ModelAdmin):
    list_display = ("assinatura", "tipo", "quantidade", "origem", "ativo", "inicio_vigencia", "fim_vigencia")
    list_filter = ("tipo", "origem", "ativo")


@admin.register(AddonCatalogo)
class AddonCatalogoAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "valor_mensal", "ativo")
    list_filter = ("ativo",)
    search_fields = ("nome", "slug")


@admin.register(AssinaturaAddon)
class AssinaturaAddonAdmin(admin.ModelAdmin):
    list_display = ("assinatura", "addon", "quantidade", "valor_unitario_congelado", "ativo")
    list_filter = ("ativo",)


@admin.register(FaturaMunicipio)
class FaturaMunicipioAdmin(admin.ModelAdmin):
    list_display = ("municipio", "competencia", "valor_total", "status", "gerada_em", "paga_em")
    list_filter = ("status", "competencia")
    search_fields = ("municipio__nome",)
