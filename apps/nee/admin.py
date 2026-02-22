from django.contrib import admin

from .models import (
    AcompanhamentoNEE,
    AlunoNecessidade,
    ApoioMatricula,
    LaudoNEE,
    RecursoNEE,
    TipoNecessidade,
)


@admin.register(TipoNecessidade)
class TipoNecessidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo")
    search_fields = ("nome",)
    list_filter = ("ativo",)


@admin.register(AlunoNecessidade)
class AlunoNecessidadeAdmin(admin.ModelAdmin):
    list_display = ("aluno", "tipo", "cid", "ativo")
    search_fields = ("aluno__nome", "tipo__nome", "cid")
    list_filter = ("ativo", "tipo")


@admin.register(ApoioMatricula)
class ApoioMatriculaAdmin(admin.ModelAdmin):
    list_display = ("matricula", "tipo", "ativo")
    search_fields = ("matricula__aluno__nome", "descricao", "observacao")
    list_filter = ("ativo", "tipo")


@admin.register(LaudoNEE)
class LaudoNEEAdmin(admin.ModelAdmin):
    list_display = ("aluno", "data_emissao", "validade", "profissional")
    search_fields = ("aluno__nome", "numero", "profissional")
    list_filter = ("data_emissao",)


@admin.register(RecursoNEE)
class RecursoNEEAdmin(admin.ModelAdmin):
    list_display = ("aluno", "nome", "status")
    search_fields = ("aluno__nome", "nome")
    list_filter = ("status",)


@admin.register(AcompanhamentoNEE)
class AcompanhamentoNEEAdmin(admin.ModelAdmin):
    list_display = ("aluno", "data", "tipo_evento", "autor", "visibilidade")
    search_fields = ("aluno__nome", "descricao", "autor__username")
    list_filter = ("tipo_evento", "visibilidade", "data")
