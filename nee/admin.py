from django.contrib import admin

from .models import (
    TipoNecessidade,
    AlunoNecessidade,
    ApoioMatricula,
    LaudoNEE,
    RecursoNEE,
    AcompanhamentoNEE,
)


@admin.register(TipoNecessidade)
class TipoNecessidadeAdmin(admin.ModelAdmin):
    search_fields = ("nome",)
    list_display = ("nome", "ativo")
    list_filter = ("ativo",)


@admin.register(AlunoNecessidade)
class AlunoNecessidadeAdmin(admin.ModelAdmin):
    search_fields = ("aluno__nome", "tipo__nome", "cid")
    list_display = ("aluno", "tipo", "cid", "ativo")
    list_filter = ("ativo", "tipo")


@admin.register(ApoioMatricula)
class ApoioMatriculaAdmin(admin.ModelAdmin):
    search_fields = ("matricula__aluno__nome", "descricao")
    list_display = ("matricula", "tipo", "ativo")
    list_filter = ("ativo", "tipo")


@admin.register(LaudoNEE)
class LaudoNEEAdmin(admin.ModelAdmin):
    search_fields = ("aluno__nome", "emissor", "numero")
    list_display = ("aluno", "tipo", "data_emissao", "ativo")
    list_filter = ("ativo", "tipo")


@admin.register(RecursoNEE)
class RecursoNEEAdmin(admin.ModelAdmin):
    search_fields = ("aluno__nome", "nome", "categoria")
    list_display = ("aluno", "nome", "categoria", "ativo")
    list_filter = ("ativo",)


@admin.register(AcompanhamentoNEE)
class AcompanhamentoNEEAdmin(admin.ModelAdmin):
    search_fields = ("aluno__nome", "titulo", "descricao")
    list_display = ("aluno", "data", "status", "ativo")
    list_filter = ("ativo", "status")
