from django.contrib import admin
from .models import Municipio, Secretaria, Unidade, Setor


@admin.register(Municipio)
class MunicipioAdmin(admin.ModelAdmin):
    list_display = ("nome", "uf", "cnpj_prefeitura", "nome_prefeito", "ativo")
    search_fields = ("nome", "uf", "cnpj_prefeitura", "nome_prefeito")
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
