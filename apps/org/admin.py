from django.contrib import admin
from .models import (
    Municipio,
    Secretaria,
    Unidade,
    Setor,
    SecretariaTemplate,
    SecretariaTemplateItem,
    SecretariaProvisionamento,
    MunicipioModuloAtivo,
    SecretariaModuloAtivo,
    OnboardingStep,
)


@admin.register(Municipio)
class MunicipioAdmin(admin.ModelAdmin):
    list_display = ("nome", "uf", "slug_site", "dominio_personalizado", "ativo")
    search_fields = ("nome", "uf", "slug_site", "cnpj_prefeitura", "nome_prefeito", "dominio_personalizado")
    list_filter = ("uf", "ativo")


@admin.register(Secretaria)
class SecretariaAdmin(admin.ModelAdmin):
    list_display = ("nome", "municipio", "sigla", "ativo")
    search_fields = ("nome", "sigla", "municipio__nome")
    list_filter = ("municipio", "ativo")


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "secretaria", "codigo_inep", "ativo")
    search_fields = ("nome", "codigo_inep", "secretaria__nome")
    list_filter = ("tipo", "ativo", "secretaria")


@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    list_display = ("nome", "unidade", "ativo")
    search_fields = ("nome", "unidade__nome")
    list_filter = ("ativo", "unidade")


@admin.register(SecretariaTemplate)
class SecretariaTemplateAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "modulo", "ativo", "criar_unidade_base")
    search_fields = ("nome", "slug", "descricao")
    list_filter = ("modulo", "ativo", "criar_unidade_base")


@admin.register(SecretariaTemplateItem)
class SecretariaTemplateItemAdmin(admin.ModelAdmin):
    list_display = ("template", "tipo", "nome", "ordem", "ativo")
    search_fields = ("template__nome", "nome")
    list_filter = ("tipo", "ativo", "template")


@admin.register(SecretariaProvisionamento)
class SecretariaProvisionamentoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "template", "secretaria", "status", "solicitado_por", "criado_em")
    search_fields = ("municipio__nome", "template__nome", "secretaria__nome", "solicitado_por__username")
    list_filter = ("status", "template", "municipio")


@admin.register(MunicipioModuloAtivo)
class MunicipioModuloAtivoAdmin(admin.ModelAdmin):
    list_display = ("municipio", "modulo", "ativo", "atualizado_em")
    search_fields = ("municipio__nome", "modulo")
    list_filter = ("modulo", "ativo")


@admin.register(SecretariaModuloAtivo)
class SecretariaModuloAtivoAdmin(admin.ModelAdmin):
    list_display = ("secretaria", "modulo", "ativo", "atualizado_em")
    search_fields = ("secretaria__nome", "modulo")
    list_filter = ("modulo", "ativo")


@admin.register(OnboardingStep)
class OnboardingStepAdmin(admin.ModelAdmin):
    list_display = ("municipio", "secretaria", "modulo", "codigo", "ordem", "status")
    search_fields = ("municipio__nome", "secretaria__nome", "modulo", "codigo", "titulo")
    list_filter = ("modulo", "status")
